import streamlit as st
import pandas as pd
from sqlalchemy import text
import io
import os
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuração da página
st.set_page_config(page_title="Sistema de Lançamento de Vacinas - Dia D", layout="wide")

# Conexão com o banco de dados
try:
    conn = st.connection("postgresql", type="sql")
except Exception as e:
    st.error(f"Erro ao configurar a conexão com o banco de dados: {e}")
    conn = None

ubs_por_distrito = {
    "Distrito 1": ["Alto", "Bairro Novo I", "Bairro Novo II", "Cordeiro", "Primavera"],
    "Distrito 2": ["Juá", "Nações", "Nordeste I", "Nordeste II", "Nordeste III"],
    "Distrito 3": ["Assis", "Clóvis Bezerra", "Rosário", "São José", "Santa Terezinha"],
    "Distrito 4": ["Cachoeira", "Contendas", "Mutirão", "Pirpiri", "Tananduba"]
}

# --- FUNÇÃO DE ESTILIZAÇÃO COMPACTA E COLORIDA ---
def destacar_linhas_tabela(df):
    def aplicar_cor_linha(row):
        idx_str = str(row.name).upper()
        if 'TOTAL FINAL' in idx_str or 'TOTAL GERAL' in idx_str or 'TOTAL MUNICÍPIO' in idx_str or 'TOTALMENTE GERAL' in idx_str:
            return ['background-color: #d4edda; color: #155724; font-weight: bold; font-size: 11px;'] * len(row)
        elif 'TOTAL PARCIAL' in idx_str:
            return ['background-color: #fff3cd; color: #856404; font-weight: bold; font-size: 11px;'] * len(row)
        elif 'TOTAL DISTRITO' in idx_str:
            return ['background-color: #d1ecf1; color: #0c5460; font-weight: bold; font-size: 11px;'] * len(row)
        return ['font-size: 11px;'] * len(row)

    formatadores = {}
