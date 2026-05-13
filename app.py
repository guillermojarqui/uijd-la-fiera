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

# ================= INICIALIZAR CONTADOR DE SESIÓN (para claves únicas) =================
if "download_counter" not in st.session_state:
    st.session_state.download_counter = 0

# ================= ESTILOS (fondo azul más oscuro) =================
st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #050b14, #0a1a2a);
    }
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #D4AF37 !important;
    }
    .stButton > button {
        background-color: #D4AF37 !important;
        color: #050b14 !important;
        font-weight: bold;
        border-radius: 30px;
    }
    </style>
""", unsafe_allow_html=True)

# ================= IMAGEN DE IUSTITIA (más grande) =================
IUSTITIA_URL = "https://raw.githubusercontent.com/guillermojarqui/uijd-la-fiera/main/Iustitia.jpg"
# Ajusta el ancho aquí (por ejemplo 300, 350, etc.)
ANCHO_IMAGEN = 400

# ================= LIMPIADOR PARA PDF =================
def limpiar_para_pdf(texto):
    if not texto:
        return ""
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N", "¿": "", "¡": "",
    }
    for original, seguro in reemplazos.items():
        texto = texto.replace(original, seguro)
    return texto.encode('ascii', 'ignore').decode('ascii')

# ================= REGISTRO NACIONAL SIMULADO =================
def ejecutar_barrido_registro_nacional(nombre_sujeto, status_placeholder):
    status_placeholder.text("Buscando en el Registro Nacional (simulado)")
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
    try:
        pdf = DictamenPremium()
        pdf.add_page()

        # Imagen de Iustitia en el encabezado
        try:
            pdf.image("lustitia.jpg", x=10, y=20, w=40)  # Ajusta posición y tamaño
        except:
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 10, "Imagen Iustitia no encontrada", ln=True)

        # Encabezado
        pdf.set_font("Helvetica", 'B', 18)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 12, "DICTAMEN DE INTELIGENCIA ESTRATEGICA", 0, 1, 'C')

        pdf.set_font("Helvetica", 'B', 14)
        pdf.set_text_color(0, 31, 63)
        pdf.cell(0, 10, f"Objetivo: {objetivo.upper()}", 0, 1, 'C')
        pdf.ln(6)

        # Fecha y código
        pdf.set_font("Helvetica", '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 6, f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
        verif_id = hashlib.md5((objetivo+str(datetime.now())).encode()).hexdigest()[:8].upper()
        pdf.cell(0, 6, f"Código de verificación: UIJD-{verif_id}", 0, 1)
        pdf.ln(8)

        # Texto de prueba fijo
        pdf.set_font("Helvetica", '', 11)
        pdf.multi_cell(0, 8, "Este es un texto de prueba para confirmar que el PDF escribe correctamente. "
                             "Si ves este párrafo, significa que el problema de páginas en blanco está resuelto.")
        pdf.ln(10)

        # Resumen ejecutivo
        total_hallazgos = sum(len(h) for h in resultados.values())
        pdf.set_font("Helvetica", 'B', 14)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 8, "RESUMEN EJECUTIVO", 0, 1)
        pdf.set_font("Helvetica", '', 11)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, f"Se han identificado un total de {total_hallazgos} hallazgos a través de las capas de inteligencia consultadas.")
        pdf.ln(4)

        # Mapa de calor
        riesgo_score = calcular_mapa_calor(resultados)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 8, "MAPA DE CALOR DE RIESGO", 0, 1)
        pdf.set_font("Helvetica", '', 10)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, f"Puntuación de riesgo: {riesgo_score} / 100")
        pdf.ln(4)

        # Entidades vinculadas
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

        # Hallazgos destacados (corregido con texto de prueba)
pdf.set_font("Helvetica", 'B', 12)
pdf.set_text_color(184, 134, 11)
pdf.cell(0, 8, "HALLAZGOS DESTACADOS", 0, 1)
pdf.set_font("Helvetica", '', 9)
pdf.set_text_color(0, 0, 0)

# Texto fijo de prueba para confirmar escritura
pdf.multi_cell(0, 8, "Texto de prueba: esta sección de hallazgos está funcionando correctamente.")
pdf.ln(5)

for capa, hallazgos in resultados.items():
    if not hallazgos:
        pdf.multi_cell(0, 8, f"- {capa}: Sin hallazgos")
        pdf.ln(2)
    else:
        for h in hallazgos[:5]:  # limitar a 5 para prueba
            titulo = limpiar_para_pdf(h.get('titulo', 'Sin titulo'))
            fuente = limpiar_para_pdf(h.get('fuente', 'Sin fuente'))
            dato = limpiar_para_pdf(h.get('dato', 'Sin contenido'))
            texto_hallazgo = f"- {titulo}\nFuente: {fuente}\nExtracto: {dato}\n"
            pdf.multi_cell(0, 8, texto_hallazgo)
            pdf.ln(2)


        # Recomendaciones
        pdf.add_page()
        pdf.set_font("Helvetica", 'B', 14)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(0, 10, "RECOMENDACIONES Y CIERRE", 0, 1)
        pdf.ln(5)
        pdf.set_font("Helvetica", '', 11)
        pdf.set_text_color(0, 0, 0)
        recs = [
            "1. Verificación adicional en el Registro Nacional.",
            "2. Consultar expediente judicial en el Poder Judicial.",
            "3. Evaluar denuncia ante la UIF si hay indicios.",
            "4. Considerar auditoría forense de nivel IV."
        ]
        for r in recs:
            pdf.multi_cell(0, 7, r)

        return pdf.output(dest='S')
    except Exception as e:
        st.error(f"Error interno al generar el PDF: {e}")
        import traceback
        st.code(traceback.format_exc())
        return None



# ================= DASHBOARD PRINCIPAL =================
st.set_page_config(page_title="UIJD - Jarquin Legal Intelligence", layout="wide", page_icon=":material/balance:")

col1, col2 = st.columns([1, 3])
with col1:
    st.image(IUSTITIA_URL, width=ANCHO_IMAGEN)
with col2:
    st.markdown("""
        <div style="text-align: center;">
            <h1 style="color: #D4AF37;">Jarquin Legal Services<br><small style="color: #D4AF37;">& AI Solutions</small></h1>
            <h2 style="color: #D4AF37;">INTELIGENCIA ESTRATEGICA</h2>
            <h3 style="color: #FFE066;">Unidad de Inteligencia Juridica Digital (UIJD)</h3>
            <p style="color: #ffffff;">Barrido Forense en 8 Capas - ICIJ + Datos Abiertos Costa Rica</p>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")
objetivo = st.text_input("Ingrese nombre completo, cedula o razon social:", placeholder="Ej: Ruben Pacheco Lutz")

if st.button("INICIAR INVESTIGACION FORENSE", type="primary"):
    if objetivo and len(objetivo.strip()) >= 3:
        # Incrementar contador para claves únicas de descarga
        st.session_state.download_counter += 1
        unique_id = st.session_state.download_counter

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
            emoji = "🔥🔥🔥"
        elif riesgo_score >= 40:
            nivel = "MODERADO"
            color = "#f0ad4e"
            emoji = "🔥🔥"
        else:
            nivel = "BAJO"
            color = "#5bc0de"
            emoji = "🔥"
        st.markdown("---")
        st.markdown(f"## {emoji} MAPA DE CALOR DE RIESGO {emoji}")
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
                    nombre_manual = st.text_input("Nombre exacto", key=f"nom_{ent}_{unique_id}")
                    estado_manual = st.selectbox("Estado", ["", "INSCRITA", "MOROSA", "AL DIA"], key=f"est_{ent}_{unique_id}")
                    rep = st.text_area("Representantes", key=f"rep_{ent}_{unique_id}")
                    obs = st.text_area("Observaciones", key=f"obs_{ent}_{unique_id}")
                    if st.button("Guardar", key=f"btn_{ent}_{unique_id}"):
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
            col1.download_button("CSV", data=csv_buffer, file_name=f"hallazgos_{objetivo}.csv", mime="text/csv", key=f"csv_{unique_id}")
            # Generar PDF con manejo de errores
            try:
                pdf_bytes = generar_pdf_premium(objetivo, resultados, datos_rn)
                col2.download_button("PDF", data=pdf_bytes, file_name=f"Dictamen_{objetivo}.pdf", mime="application/pdf", key=f"pdf_{unique_id}")
            except Exception as e:
                st.error(f"Error al generar el PDF: {e}")
                st.info("Intente nuevamente o exporte los datos a CSV.")
    else:
        st.error("Ingrese al menos 3 caracteres.")
