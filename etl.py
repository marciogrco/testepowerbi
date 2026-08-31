
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

RAW_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "teste_bi_base_crua.xlsx"
OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "processed"
OUT_PATH.mkdir(parents=True, exist_ok=True)

DATA_REFERENCIA = pd.Timestamp(datetime.now().date())


def carregar_bases(path: Path) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(path)
    return {
        "associados": pd.read_excel(xls, "Associados"),
        "produtos": pd.read_excel(xls, "Produtos"),
        "movimentacao": pd.read_excel(xls, "Movimentacao"),
    }


def padronizar_cidade(cidade: str) -> str:
    """Normaliza variações de escrita da mesma cidade (ex.: 'P. Branco',
    'PATO BRANCO', 'Pato Branco' -> 'Pato Branco')."""
    if pd.isna(cidade):
        return cidade
    c = str(cidade).strip()
    mapa = {
        "P. BRANCO": "Pato Branco",
        "PATO BRANCO": "Pato Branco",
    }
    return mapa.get(c.upper(), c.title())


def tratar_associados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Duplicados: mantém o primeiro registro por CHAVE (chave é o identificador único)
    antes = len(df)
    df = df.drop_duplicates(subset="CHAVE", keep="first")
    df = df.drop_duplicates()
    dup_removidos = antes - len(df)

    # Padronização de texto
    df["NOME"] = df["NOME"].astype(str).str.strip().str.title()
    df["CIDADE"] = df["CIDADE"].apply(padronizar_cidade)
    df["AGENCIA"] = df["AGENCIA"].astype(str).str.zfill(2)

    # Datas: corrige eventuais datas de associação futuras (erro de digitação)
    df["DATA_ASSOCIACAO"] = pd.to_datetime(df["DATA_ASSOCIACAO"], errors="coerce")
    datas_futuras = (df["DATA_ASSOCIACAO"] > DATA_REFERENCIA).sum()
    df.loc[df["DATA_ASSOCIACAO"] > DATA_REFERENCIA, "DATA_ASSOCIACAO"] = pd.NaT

    # Valores nulos de renda: imputados pela mediana
    nulos_renda = df["RENDA_MENSAL"].isna().sum()
    mediana_renda = df["RENDA_MENSAL"].median()
    df["RENDA_MENSAL"] = df["RENDA_MENSAL"].fillna(mediana_renda)

    print(f"[Associados] duplicados removidos: {dup_removidos} | "
          f"datas futuras corrigidas: {datas_futuras} | "
          f"rendas nulas imputadas (mediana={mediana_renda:.2f}): {nulos_renda}")
    return df


def tratar_produtos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    antes = len(df)
    df = df.drop_duplicates(subset="CHAVE", keep="first")
    dup_removidos = antes - len(df)

    colunas_produto = ["CONTA_CORRENTE", "CARTAO", "CREDITO", "INVESTIMENTO", "CONSORCIO", "SEGURO"]
    for c in colunas_produto:
        df[c] = df[c].astype(str).str.strip().str.upper().map({"S": "Sim", "N": "Não"}).fillna("Não")

    print(f"[Produtos] duplicados removidos: {dup_removidos}")
    return df, colunas_produto


def tratar_movimentacao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    antes = len(df)
    df = df.drop_duplicates(subset="CHAVE", keep="first")
    dup_removidos = antes - len(df)

    for c in ["SALDO_MEDIO", "PIX_MENSAL", "COMPRAS_CARTAO"]:
        nulos = df[c].isna().sum()
        df[c] = df[c].fillna(0)
        if nulos:
            print(f"[Movimentacao] {c}: {nulos} nulos preenchidos com 0")

    print(f"[Movimentacao] duplicados removidos: {dup_removidos}")
    return df


def faixa_renda(renda: float) -> str:
    if renda <= 3000:
        return "Até R$ 3.000"
    if renda <= 8000:
        return "R$ 3.001 a R$ 8.000"
    if renda <= 15000:
        return "R$ 8.001 a R$ 15.000"
    return "Acima de R$ 15.000"


def classificar(row) -> str:
    """
    Metodologia de classificação (documentada no README):

    Combina 3 eixos: nº de produtos ativos, tempo de relacionamento (anos) e intensidade de uso (saldo médio + movimentação via PIX/cartão).

    - Engajado: uso muito alto (score de uso no top 25%) E 4+ produtos -> maior diversificação e atividade financeira, independente do tempo de casa.
    - Maduro: 4+ produtos E mais de 3 anos de relacionamento E saldo médio acima da mediana.
    - Em Desenvolvimento: 2 a 3 produtos, relacionamento em crescimento (>= 1 ano) e uso moderado.
    - Inicial: até 1 produto, menos de 2 anos de relacionamento ou uso baixo.
    - Demais casos: Em Desenvolvimento (classe intermediária padrão).
    """
    qtd_produtos = row["QTD_PRODUTOS"]
    anos = row["TEMPO_RELACIONAMENTO_ANOS"]
    uso_alto = row["USO_ALTO"]
    saldo_acima_mediana = row["SALDO_ACIMA_MEDIANA"]

    if uso_alto and qtd_produtos >= 4:
        return "Engajado"
    if qtd_produtos >= 4 and anos > 3 and saldo_acima_mediana:
        return "Maduro"
    if qtd_produtos <= 1 and (pd.isna(anos) or anos < 2):
        return "Inicial"
    if 2 <= qtd_produtos <= 3:
        return "Em Desenvolvimento"
    return "Em Desenvolvimento"


def gerar_indicadores(assoc: pd.DataFrame, prod: pd.DataFrame, mov: pd.DataFrame,
                       colunas_produto: list[str]) -> pd.DataFrame:
    prod = prod.copy()
    prod["QTD_PRODUTOS"] = (prod[colunas_produto] == "Sim").sum(axis=1)

    base = assoc.merge(prod[["CHAVE", "QTD_PRODUTOS"] + colunas_produto], on="CHAVE", how="left")
    base = base.merge(mov, on="CHAVE", how="left")

    base["TEMPO_RELACIONAMENTO_ANOS"] = (
        (DATA_REFERENCIA - base["DATA_ASSOCIACAO"]).dt.days / 365.25
    ).round(1)

    base["FAIXA_RENDA"] = base["RENDA_MENSAL"].apply(faixa_renda)

    # Score de uso: combina saldo médio, PIX mensal e compras no cartão (normalizados)
    for c in ["SALDO_MEDIO", "PIX_MENSAL", "COMPRAS_CARTAO"]:
        base[f"{c}_NORM"] = (base[c] - base[c].min()) / (base[c].max() - base[c].min())
    base["SCORE_USO"] = base[["SALDO_MEDIO_NORM", "PIX_MENSAL_NORM", "COMPRAS_CARTAO_NORM"]].mean(axis=1)
    base["USO_ALTO"] = base["SCORE_USO"] >= base["SCORE_USO"].quantile(0.75)
    base["SALDO_ACIMA_MEDIANA"] = base["SALDO_MEDIO"] >= base["SALDO_MEDIO"].median()

    base["CLASSIFICACAO"] = base.apply(classificar, axis=1)

    base = base.drop(columns=[c for c in base.columns if c.endswith("_NORM")] + ["SCORE_USO"])
    return base


def main():
    bases = carregar_bases(RAW_PATH)
    assoc = tratar_associados(bases["associados"])
    prod, colunas_produto = tratar_produtos(bases["produtos"])
    mov = tratar_movimentacao(bases["movimentacao"])

    base_consolidada = gerar_indicadores(assoc, prod, mov, colunas_produto)

    assoc.to_csv(OUT_PATH / "associados_tratado.csv", index=False)
    prod.to_csv(OUT_PATH / "produtos_tratado.csv", index=False)
    mov.to_csv(OUT_PATH / "movimentacao_tratado.csv", index=False)
    base_consolidada.to_csv(OUT_PATH / "base_consolidada.csv", index=False)
    base_consolidada.to_excel(OUT_PATH / "base_consolidada.xlsx", index=False)

    print(f"\nBase consolidada gerada com {len(base_consolidada)} associados.")
    print(base_consolidada["CLASSIFICACAO"].value_counts())


if __name__ == "__main__":
    main()
