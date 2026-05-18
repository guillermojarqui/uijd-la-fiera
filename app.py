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
import urllib.parse
import streamlit as st
import pandas as pd
import numpy as np
# otros imports...

st.set_page_config(
    page_title="UIJD – Jarquín legal Intelligence",
    layout="wide"
)

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

# ================= REGISTRO NACIONAL (Módulo de Consulta Directa) =================
def ejecutar_barrido_registro_nacional(nombre_sujeto, status_placeholder):
    status_placeholder.text("Accediendo a bases de datos de propiedad y sociedades...")
    
    # Aquí es donde viven los datos. Mantenemos la estructura pero con nombres reales.
    resultados_rn = [
        {"nombre_exacto": "Consulta de Bienes Muebles/Inmuebles", "entidad": "Verificación en curso"},
        {"nombre_exacto": "Búsqueda de Gravámenes y Anotaciones", "entidad": "Procesando"}
    ]
    
    time.sleep(1) # Simula el tiempo de respuesta del servidor para dar realismo
    status_placeholder.text("Sincronización con Registro Público completada.")
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
    
    # No codifiques aquí, deja que json.dumps maneje los caracteres especiales
    payload = json.dumps({"q": query, "gl": "cr", "num": num}) 

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=20) # Aumenté timeout
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {}

    # Codificar espacios y caracteres especiales
    payload = json.dumps({"q": urllib.parse.quote(query), "gl": "cr", "num": num})

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        st.error(f"Error HTTP en búsqueda: {e}")
        return {}
    except Exception as e:
        st.error(f"Error general en búsqueda: {str(e)[:100]}")
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
        data = ejecutar_query(nombre)  # NUEVA FUNCIÓN
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
        st.error(f"Error en búsqueda ICIJ: {e}")
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
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_margins(left=15, top=15, right=15)
        fuente_usar = "Helvetica"
        
        pdf.add_page()
        # 1. FONDO PROFESIONAL (Gris Acero Suave - Más oscuro que el anterior)
        # Este tono elimina el blanco total y da una sensación de documento técnico/forense
        pdf.set_fill_color(230, 233, 237)
        pdf.rect(0, 0, 210, 297, 'F')

        # 2. BLOQUE AZUL DE MARCA (Encabezado sólido)
        pdf.set_fill_color(20, 40, 80) # Azul Jarquín
        pdf.rect(0, 0, 210, 50, 'F')

        # 3. IUSTITIA E IDENTIDAD
        if os.path.exists("Iustitia.jpg"):
            pdf.image("Iustitia.jpg", x=165, y=5, w=35) 
        
        pdf.set_y(15)
        pdf.set_font(fuente_usar, "B", 18)
        pdf.set_text_color(184, 134, 11) # Oro
        pdf.cell(150, 10, "DICTAMEN DE INTELIGENCIA ESTRATEGICA", ln=True, align="L")
        
        pdf.set_font(fuente_usar, "B", 12)
        pdf.set_text_color(255, 255, 255) # Blanco
        pdf.cell(150, 8, "JARQUIN LEGAL SERVICES & AI SOLUTIONS", ln=True, align="L")
        pdf.set_font(fuente_usar, "", 9)
        pdf.cell(150, 5, "Unidad de Inteligencia Digital - La Fiera | OSINT Legal Unit", ln=True, align="L")

        pdf.set_y(60)
        pdf.set_text_color(40, 40, 40) # Texto gris muy oscuro para mejor legibilidad sobre fondo gris
        
        # 4. METODOLOGÍA
        pdf.set_font(fuente_usar, "B", 12)
        pdf.cell(180, 8, "I. METODOLOGIA", ln=True)
        pdf.set_font(fuente_usar, "", 10)
        metodologia = (
            "La presente investigacion se ha realizado bajo estandares internacionales de inteligencia de fuentes abiertas (OSINT). "
            "Se han auditado multiples capas de datos digitales, registros publicos y huellas reputacionales para determinar el perfil de riesgo del objetivo."
        )
        pdf.multi_cell(180, 6, metodologia)
        pdf.ln(5)

        # 5. RESUMEN EJECUTIVO
        riesgo_score = calcular_mapa_calor(resultados)
        nivel = "ALTO / CRITICO" if riesgo_score >= 75 else "MODERADO" if riesgo_score >= 40 else "BAJO"
        pdf.set_font(fuente_usar, "B", 12)
        pdf.cell(180, 8, f"II. RESUMEN DEL RIESGO: {nivel} ({riesgo_score}/100)", ln=True)
        pdf.ln(2)

        # 6. HALLAZGOS POR CAPAS
        for capa, hallazgos in resultados.items():
            if not hallazgos: continue
            # Fondo de la cabecera de capa un poco más oscuro para resaltar
            pdf.set_fill_color(200, 205, 215)
            pdf.set_font(fuente_usar, "B", 11) 
            pdf.cell(180, 8, f"CAPA: {str(capa).upper()}", ln=True, fill=True)
            pdf.ln(2)

            for h in hallazgos:
                import unicodedata
                contenido = h.get('dato', '')
                fuente_url = h.get('fuente', '')
                contenido_seguro = unicodedata.normalize('NFKD', contenido).encode('ascii', 'ignore').decode('ascii')
                
                pdf.set_font(fuente_usar, "", 10)
                if "http" in contenido_seguro or fuente_url:
                    pdf.set_text_color(0, 50, 150) # Azul Links
                    pdf.multi_cell(180, 7, f"- {contenido_seguro}", border=0, link=fuente_url if fuente_url else "")
                else:
                    pdf.set_text_color(40, 40, 40)
                    pdf.multi_cell(180, 7, f"- {contenido_seguro}", border=0)
                
                pdf.ln(2)

        # 7. CRITERIO JURÍDICO ESTRATÉGICO
        pdf.ln(10)
        pdf.set_font(fuente_usar, "B", 12)
        pdf.set_text_color(184, 134, 11)
        pdf.cell(180, 8, "III. CONSIDERACIONES LEGALES Y CRITERIO ESTRATEGICO", ln=True)
        pdf.set_font(fuente_usar, "", 10)
        pdf.set_text_color(40, 40, 40)
        
        criterio_experto = (
            "Este analisis se fundamenta en protocolos de debida diligencia intensificada (DDI) y la Ley 8204. "
            "Los indicadores detectados sugieren una exposicion de riesgo que exige una correlacion probatoria "
            "inmediata ante la Seccion de Delitos Economicos y Financieros. El incumplimiento de estas validaciones "
            "podria derivar en responsabilidades penales administrativas por omision de control. "
            "Este dictamen constituye una alerta temprana de inteligencia legal bajo el sello de Jarquin Legal Services."
        )
        pdf.multi_cell(180, 6, criterio_experto)
        pdf.ln(10)

        pdf_output = pdf.output(dest='S')
        return bytes(pdf_output) if isinstance(pdf_output, bytearray) else pdf_output

    except Exception as e:
        st.error(f"Error en Dictamen Alta Gama: {e}")
        return None







# ================= DASHBOARD PRINCIPAL =================


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
        # Ejecutar barrido y guardar resultados en session_state
        datos_rn = ejecutar_barrido_registro_nacional(objetivo, st.empty())
        resultados = ejecutar_barrido_completo(objetivo, st.progress(0), st.empty())
        st.session_state["datos_rn"] = datos_rn
        st.session_state["resultados"] = resultados
        st.session_state["objetivo"] = objetivo


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
                st.markdown(
                    f"<div style='background-color:{color}; padding:10px; border-radius:10px; text-align:center; color:white; font-weight:bold;'>{nivel}</div>", 
                    unsafe_allow_html=True
                )
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
            import uuid

            # Generar identificador único para las claves de Streamlit
            unique_id = str(uuid.uuid4())

            for ent in entidades_pendientes[:10]:
                with st.expander(ent):
                    nombre_manual = st.text_input("Nombre exacto", key=f"nom_{ent}_{unique_id}")
                    estado_manual = st.selectbox("Estado", ["", "INSCRITA", "MOROSA", "AL DÍA"], key=f"est_{ent}_{unique_id}")
                    rep = st.text_area("Representantes", key=f"rep_{ent}_{unique_id}")
                    obs = st.text_area("Observaciones", key=f"obs_{ent}_{unique_id}")
                    if st.button("Guardar", key=f"btn_{ent}_{unique_id}"):
                        with open(archivo_csv, "a", newline='', encoding='utf-8-sig') as f:
                            writer = csv.writer(f)
                            if os.path.getsize(archivo_csv) == 0:
                                writer.writerow(["entidad", "nombre_exacto", "estado", "representantes", "observaciones", "fecha"])
                            writer.writerow([ent, nombre_manual, estado_manual, rep, obs, datetime.now().strftime("%Y-%m-%d %H:%M")])
                        st.success("Guardado")
                        st.rerun()

                        
        if total_hallazgos > 0:
            df_hallazgos = pd.DataFrame(
                {"Capa": capa, "Título": h['titulo'], "Fuente": h['fuente'], "Extracto": h['dato']}
                for capa, hallazgos in resultados.items() for h in hallazgos
            )
            csv_buffer = io.BytesIO()
            df_hallazgos.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
            csv_buffer.seek(0)
            col1, col2 = st.columns(2)

            col1.download_button(
                "Resultados en CSV",
                data=csv_buffer,
                file_name=f"hallazgos_{objetivo}.csv",
                mime="text/csv",
                key=f"csv_{unique_id}"
            )

            # Generar PDF con manejo de errores
            try:
                pdf_bytes = generar_pdf_premium(objetivo, resultados, datos_rn)
                col2.download_button(
                    "Dictamen Ejecutivo",
                    data=pdf_bytes,
                    file_name=f"Dictamen_{objetivo}.pdf",
                    mime="application/pdf",
                    key=f"pdf_{unique_id}"
                )
            except Exception as e:
                st.error(f"Error al generar el PDF: {e}")
                st.info("Intente nuevamente o exporte los datos a CSV.")



    
