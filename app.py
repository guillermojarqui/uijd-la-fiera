import streamlit as st
import requests
import json
import time
import pandas as pd
from fpdf import FPDF
import io
import hashlib
from datetime import datetime
import re
import csv
import os

def limpiar_para_pdf(texto):
    if not texto:
        return ""
    reemplazos = {
        "-": "-", "--": "-", '"': '"', "'": "'",
        "a": "a", "e": "e", "i": "i", "o": "o", "u": "u",
        "A": "A", "E": "E", "I": "I", "O": "O", "U": "U",
        "n": "n", "N": "N", "o": "o", "a": "a", "?": "", "!": "",
        "E": "e", "°": " ", "...": "..."
    }
    for original, seguro in reemplazos.items():
        texto = texto.replace(original, seguro)
    return texto.encode('ascii', 'ignore').decode('ascii')

def ejecutar_barrido_registro_nacional(nombre_sujeto, status_placeholder):
    status_placeholder.text("Buscando en el Registro Nacional (modo simulado)")
    resultados_rn = [
        {"nombre_exacto": "Sociedad de Ejemplo S.A.", "entidad": "3-101-654321"},
        {"nombre_exacto": "Inversiones Virtuales Ltda.", "entidad": "3-102-987654"}
    ]
    status_placeholder.text("Barrido simulado completado")
    return resultados_rn

class DictamenPremium(FPDF):
    def header(self):
        self.set_fill_color(0, 31, 63)
        self.rect(0, 0, 210, 50, 'F')
        self.set_fill_color(184, 134, 11)
        self.rect(0, 50, 210, 3, 'F')
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(184, 134, 11)
        self.cell(0, 30, 'DICTAMEN DE INTELIGENCIA ESTRATEGICA', 0, 1, 'C')
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, -10, 'JARQUIN LEGAL SERVICES & AI SOLUTIONS | OSINT UNIT', 0, 1, 'C')
        self.ln(35)
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Documento Confidencial - Pagina {self.page_no()}', 0, 0, 'C')

SERPER_API_KEY = "97d64a29b4de5ddd082fa1d71cb7374c111e1e22"

def buscar_serper(query, num=10):
    url = "https://google.serper.dev/search"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    payload = json.dumps({"q": query, "gl": "cr", "num": num})
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.warning(f"Error en busqueda: {str(e)[:100]}")
        return {}

def extraer_resultados(data):
    resultados = []
    if "organic" in data:
        for item in data["organic"]:
            resultados.append({
                "titulo": limpiar_para_pdf(item.get("title", "")),
                "fuente": item.get("link", ""),
                "dato": limpiar_para_pdf(item.get("snippet", ""))
            })
    return resultados

def capa_icij_offshore(objetivo):
    query = f'"{objetivo}" (offshoreleaks.icij.org OR "Panama Papers" OR "Pandora Papers")'
    return extraer_resultados(buscar_serper(query, 10))

def capa_jurisdicciones_opacas(objetivo):
    query = f'"{objetivo}" (BVI OR "Cayman Islands" OR Panama OR Delaware) ("registered agent" OR "offshore company")'
    return extraer_resultados(buscar_serper(query, 8))

def capa_sicop(objetivo):
    query = f'"{objetivo}" site:sicop.go.cr (adjudicacion OR licitacion)'
    return extraer_resultados(buscar_serper(query, 10))

def capa_hacienda(objetivo):
    query = f'"{objetivo}" site:hacienda.go.cr (morosidad OR deudor)'
    return extraer_resultados(buscar_serper(query, 10))

def capa_jurisprudencia(objetivo):
    query = f'"{objetivo}" (site:pgrweb.go.cr OR site:scij.poder-judicial.go.cr) (sentencia OR expediente)'
    return extraer_resultados(buscar_serper(query, 10))

def capa_prensa_riesgo(objetivo):
    query = f'"{objetivo}" (corrupcion OR lavado OR investigacion OR fraude) -facebook -instagram'
    return extraer_resultados(buscar_serper(query, 12))

def capa_tse(objetivo):
    query = f'"{objetivo}" site:tse.go.cr (sociedad OR "persona juridica")'
    return extraer_resultados(buscar_serper(query, 8))

def extraer_cedulas(texto):
    return set(re.findall(r'\b(\d{1}-\d{3}-\d{6})\b', texto))

def extraer_nombres_personas(texto):
    patron = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'
    return set(re.findall(patron, texto))

def extraer_empresas(texto):
    patron = r'\b((?:[A-Z0-9][A-Z0-9\s\.\-]*?)(?:S\.A\.|S\.A|S\.R\.L\.|SRL|LTDA|LIMITADA|SOCIEDAD ANONIMA))\b'
    coincidencias = re.findall(patron, texto, re.IGNORECASE)
    resultados = set()
    for c in coincidencias:
        c_limpio = c.strip()
        if len(c_limpio) >= 5 and not re.match(r'^(la|el|los|las|un|una)\s', c_limpio.lower()):
            resultados.add(c_limpio)
    return resultados

def buscar_en_icij(nombre, tipo="entity"):
    url = "https://offshoreleaks.icij.org/api/v1/reconcile"
    params = {"query": nombre, "type": tipo, "limit": 20}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        resultados = []
        for candidato in data.get("result", []):
            resultados.append({
                "nombre": candidato.get("name", "N/A"),
                "tipo": candidato.get("type", [{}])[0].get("name", "N/A") if candidato.get("type") else "N/A",
                "jurisdiccion": candidato.get("jurisdiction", "N/A"),
                "vinculo": candidato.get("country", "N/A"),
                "dataset": candidato.get("dataset", "N/A"),
                "score": candidato.get("score", 0)
            })
        return resultados
    except Exception as e:
        st.warning(f"Error ICIJ: {e}")
        return []

def calcular_mapa_calor(resultados):
    puntuacion = 0
    factores = {
        "ICIJ Offshore Leaks": 35,
        "Jurisdicciones Opacas": 25,
        "Prensa y Riesgo Reputacional": 20,
        "Hacienda - Morosidad": 10,
        "PGR/SCIJ - Jurisprudencia": 10
    }
    for capa, peso in factores.items():
        hallazgos = resultados.get(capa, [])
        if hallazgos:
            puntuacion += peso if len(hallazgos) > 3 else peso * 0.5
    return min(puntuacion, 100)

def ejecutar_barrido_completo(objetivo, progress_bar, status_text):
    capas = {
        "ICIJ Offshore Leaks": capa_icij_offshore,
        "Jurisdicciones Opacas": capa_jurisdicciones_opacas,
        "SICOP - Contratacion Publica": capa_sicop,
        "Hacienda - Morosidad": capa_hacienda,
        "PGR/SCIJ - Jurisprudencia": capa_jurisprudencia,
        "Prensa y Riesgo Reputacional": capa_prensa_riesgo,
        "TSE - Registro de Sociedades": capa_tse,
    }
    resultados = {}
    total = len(capas)
    for i, (nombre, func) in enumerate(capas.items()):
        status_text.text(f"Escaneando: {nombre}...")
        resultados[nombre] = func(objetivo)
        progress_bar.progress((i + 1) / total)
        time.sleep(0.3)
    return resultados

def generar_pdf_premium(objetivo, resultados, datos_registro=None):
    if datos_registro is None:
        datos_registro = []
    pdf = DictamenPremium()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 18)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 12, "DICTAMEN DE INTELIGENCIA ESTRATEGICA", 0, 1, 'C')
    pdf.set_font("Helvetica", 'B', 14)
    pdf.set_text_color(0, 31, 63)
    pdf.cell(0, 10, f"Objetivo: {objetivo.upper()}", 0, 1, 'C')
    pdf.ln(6)
    pdf.set_font("Helvetica", '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 6, f"Fecha de emision: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
    verif_id = hashlib.md5((objetivo+str(datetime.now())).encode()).hexdigest()[:8].upper()
    pdf.cell(0, 6, f"Codigo de verificacion: UIJD-{verif_id}", 0, 1)
    pdf.ln(8)
    pdf.set_font("Helvetica", 'B', 14)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 8, "RESUMEN EJECUTIVO", 0, 1)
    pdf.set_font("Helvetica", '', 11)
    pdf.set_text_color(0, 0, 0)
    total_hallazgos = sum(len(h) for h in resultados.values())
    pdf.multi_cell(0, 6, f"Se han identificado un total de {total_hallazgos} hallazgos a traves de las capas de inteligencia consultadas.")
    pdf.ln(4)
    riesgo_score = calcular_mapa_calor(resultados)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 8, "MAPA DE CALOR DE RIESGO", 0, 1)
    pdf.set_font("Helvetica", '', 10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 6, f"Puntuacion de riesgo: {riesgo_score} / 100")
    pdf.ln(4)
    if datos_registro:
        pdf.set_font("Helvetica", 'B', 12)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 8, "ENTIDADES VINCULADAS (REGISTRO NACIONAL)", 0, 1)
        pdf.set_font("Helvetica", '', 10)
        pdf.set_text_color(0, 0, 0)
        for ent in datos_registro:
            nombre = ent.get('nombre_exacto', 'N/D')
            cedula = ent.get('entidad', 'N/D')
            texto_seguro = limpiar_para_pdf(f"- {nombre} (ID: {cedula})")
            pdf.multi_cell(0, 5, txt=texto_seguro, border=0, align='L')
        pdf.ln(4)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 8, "HALLAZGOS DESTACADOS", 0, 1)
    pdf.set_font("Helvetica", '', 9)
    pdf.set_text_color(0, 0, 0)
    for capa, hallazgos in resultados.items():
        for h in hallazgos:
            texto_hallazgo = f"• {h['titulo']}\nFuente: {h['fuente']}\nExtracto: {h['dato']}\n"
            pdf.multi_cell(0, 8, limpiar_para_pdf(texto_hallazgo))
            pdf.ln(2)
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 14)
    pdf.set_text_color(184, 134, 11)
    pdf.cell(0, 10, "RECOMENDACIONES Y CIERRE", 0, 1)
    pdf.ln(5)
    pdf.set_font("Helvetica", '', 11)
    pdf.set_text_color(0, 0, 0)
    recs = [
        "1. Realizar una verificacion adicional en el Registro Nacional de las cedulas detectadas.",
        "2. Consultar el expediente judicial en el Poder Judicial para obtener detalles de procesos.",
        "3. Evaluar la pertinencia de una denuncia ante la UIF si se detectan indicios de legitimacion.",
        "4. Considerar una auditoria forense de nivel IV para profundizar en conexiones offshore."
    ]
    for r in recs:
        pdf.multi_cell(0, 7, r)
    pdf.ln(20)
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(0, 5, "-"*40, 0, 1, 'C')
    pdf.cell(0, 5, "GUILLERMO JARQUIN NUNEZ", 0, 1, 'C')
    pdf.set_font("Helvetica", '', 9)
    pdf.cell(0, 5, "Legal Tech Architect | AI Strategy Consultant", 0, 1, 'C')
    return pdf.output(dest='S')

st.set_page_config(page_title="UIJD - Jarquin Legal Intelligence", layout="wide", page_icon=":material/balance:")

st.markdown("""
    <style>
    .firma-dorado { font-family: 'Montserrat', 'Georgia', serif; font-size: 3.8rem; font-weight: 800; color: #D4AF37; text-align: center; }
    .inteligencia { font-family: 'Montserrat', serif; font-size: 1.5rem; font-weight: 600; color: #D4AF37; text-align: center; }
    .ui-titulo { font-family: 'Montserrat', sans-serif; font-size: 1.6rem; font-weight: 700; color: #FFE066; text-align: center; }
    .ui-desc { font-family: 'Montserrat', sans-serif; font-size: 1rem; color: #4a4a4a; text-align: center; }
    hr.oro { border: none; height: 3px; background: linear-gradient(90deg, transparent, #D4AF37, #b8860b, #D4AF37, transparent); }
    </style>
""", unsafe_allow_html=True)

col_img, col_text = st.columns([1.2, 2.5])
with col_img:
    st.image("https://placekitten.com/400/300", width=400)
with col_text:
    st.markdown('<div class="firma-dorado">Jarquin Legal Services<br><small>& AI Solutions</small></div>', unsafe_allow_html=True)
    st.markdown('<div class="inteligencia">INTELIGENCIA ESTRATEGICA</div>', unsafe_allow_html=True)
    st.markdown('<div class="ui-titulo">Unidad de Inteligencia Juridica Digital (UIJD)</div>', unsafe_allow_html=True)
    st.markdown('<div class="ui-desc">Barrido Forense en 8 Capas - ICIJ + Datos Abiertos Costa Rica</div>', unsafe_allow_html=True)

st.markdown('<hr class="oro">', unsafe_allow_html=True)

objetivo = st.text_input("Ingrese nombre completo, cedula o razon social:", placeholder="Ej: Ruben Pacheco Lutz")

if st.button("INICIAR INVESTIGACION FORENSE", type="primary"):
    if objetivo and len(objetivo.strip()) >= 3:
        status_text = st.empty()
        with st.spinner("Iniciando Motor de Extraccion (Registro Nacional)..."):
            datos_rn = ejecutar_barrido_registro_nacional(objetivo, status_text)
        progress_bar = st.progress(0)
        resultados = ejecutar_barrido_completo(objetivo, progress_bar, status_text)
        progress_bar.empty()
        status_text.empty()
        total_hallazgos = sum(len(v) for v in resultados.values())
        if total_hallazgos == 0:
            st.warning("No se encontraron registros. Se recomienda auditoria manual.")
        else:
            st.success(f"Barrido completado. {total_hallazgos} hallazgos encontrados.")
        riesgo_score = calcular_mapa_calor(resultados)
        if riesgo_score >= 75:
            nivel = "ALTO / CRITICO"
            color = "#d9534f"
            emoji = ""
        elif riesgo_score >= 40:
            nivel = "MODERADO"
            color = "#f0ad4e"
            emoji = ""
        else:
            nivel = "BAJO"
            color = "#5bc0de"
            emoji = ""
        st.markdown("---")
        st.markdown(f"## MAPA DE CALOR DE RIESGO")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"**Puntuacion de riesgo:** {riesgo_score} / 100")
            st.progress(riesgo_score / 100)
        with col2:
            st.markdown(f"<div style='background-color:{color}; padding:10px; border-radius:10px; text-align:center; color:white; font-weight:bold;'>{nivel}</div>", unsafe_allow_html=True)
        with st.expander("Como se calcula?"):
            st.markdown("""
            - **ICIJ Offshore Leaks** (peso 35)
            - **Jurisdicciones Opacas** (peso 25)
            - **Prensa y Riesgo Reputacional** (peso 20)
            - **Hacienda - Morosidad** (peso 10)
            - **PGR/SCIJ - Jurisprudencia** (peso 10)
            *Si una capa tiene mas de 3 hallazgos, aporta el peso completo; si tiene 1-3, aporta la mitad. Maximo 100 puntos.*
            """)
        st.markdown("---")
        tabs = st.tabs(list(resultados.keys()) + ["ICIJ", "Entidades", "Registro Manual"])
        for i, (capa, hallazgos) in enumerate(resultados.items()):
            with tabs[i]:
                if not hallazgos:
                    st.info("Sin hallazgos.")
                else:
                    riesgo_capa = "Alto" if len(hallazgos) > 3 else "Medio" if len(hallazgos) > 0 else "Bajo"
                    color_capa = "#d9534f" if riesgo_capa == "Alto" else "#f0ad4e" if riesgo_capa == "Medio" else "#5bc0de"
                    st.markdown(f"<span style='background-color:{color_capa}; padding:5px 10px; border-radius:15px; color:white;'>Exposicion en esta capa: {riesgo_capa}</span>", unsafe_allow_html=True)
                    for h in hallazgos:
                        with st.expander(f"{h['titulo'][:80]}"):
                            st.markdown(f"**Fuente:** [{h['fuente']}]({h['fuente']})")
                            st.markdown(f"**Hallazgo:** {h['dato']}")
        with tabs[len(resultados)]:
            st.subheader("ICIJ - Offshore Leaks")
            icij_results = buscar_en_icij(objetivo)
            if icij_results:
                st.dataframe(pd.DataFrame(icij_results))
            else:
                st.info("No se encontraron coincidencias.")
        with tabs[len(resultados)+1]:
            st.subheader("Entidades extraidas")
            texto_completo = " ".join([h['dato'] for capa in resultados for h in resultados[capa]])
            cedulas = extraer_cedulas(texto_completo)
            nombres = extraer_nombres_personas(texto_completo)
            empresas = extraer_empresas(texto_completo)
            if cedulas:
                st.write("**Cedulas:**")
                for c in cedulas: st.code(c)
            if nombres:
                st.write("**Nombres:**")
                for n in nombres: st.code(n)
            if empresas:
                st.write("**Empresas:**")
                for e in empresas: st.code(e)
        with tabs[len(resultados)+2]:
            st.subheader("Registro Nacional Manual")
            archivo_csv = "datos_registro_manual.csv"
            if os.path.exists(archivo_csv):
                st.dataframe(pd.read_csv(archivo_csv, encoding='utf-8-sig'))
            entidades_pendientes = list(cedulas) + list(nombres) + list(empresas)
            for ent in entidades_pendientes[:10]:
                with st.expander(ent):
                    nombre_manual = st.text_input("Nombre exacto", key=f"nom_{ent}")
                    estado_manual = st.selectbox("Estado", ["", "INSCRITA", "MOROSA", "AL DIA"], key=f"est_{ent}")
                    rep = st.text_area("Representantes", key=f"rep_{ent}")
                    obs = st.text_area("Observaciones", key=f"obs_{ent}")
                    if st.button("Guardar", key=f"btn_{ent}"):
                        with open(archivo_csv, "a", newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f)
                            if os.path.getsize(archivo_csv) == 0:
                                writer.writerow(["entidad","nombre_exacto","estado","representantes","observaciones","fecha"])
                            writer.writerow([ent, nombre_manual, estado_manual, rep, obs, datetime.now().strftime("%Y-%m-%d %H:%M")])
                        st.success("Guardado")
                        st.rerun()
        if total_hallazgos > 0:
            df_hallazgos = pd.DataFrame([
                {"Capa": capa, "Titulo": h['titulo'], "Fuente": h['fuente'], "Extracto": h['dato']}
                for capa, hallazgos in resultados.items() for h in hallazgos
            ])
            csv_buffer = io.BytesIO()
            df_hallazgos.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_buffer.seek(0)
            col1, col2 = st.columns(2)
            col1.download_button("CSV", data=csv_buffer, file_name=f"hallazgos_{objetivo}.csv", mime="text/csv")
            pdf_bytes = generar_pdf_premium(objetivo, resultados, datos_rn)
            col2.download_button("PDF", data=pdf_bytes, file_name=f"Dictamen_{objetivo}.pdf", mime="application/pdf")
    else:
        st.error("Ingrese al menos 3 caracteres.")
