import os
import re
import json
from fastapi import FastAPI, HTTPException, Request # Asegúrate de que 'Request' esté importado
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# --- Carga de Variables de Entorno y Configuración de FastAPI/Gemini (mantener igual) ---
load_dotenv()
app = FastAPI(
    title="API de Clasificación y Respuesta de Correos",
    description="API para clasificar correos electrónicos y generar respuestas "
                "automáticas usando Google Gemini.",
    version="1.0.0",
)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "La variable de entorno GOOGLE_API_KEY no está configurada. "
        "Asegúrate de tener un archivo .env con GOOGLE_API_KEY='tu_clave_aqui'."
    )
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY)

# --- Modelos Pydantic (mantener igual) ---
class EmailInput(BaseModel):
    subject: str
    body: str

class ResponseInput(BaseModel):
    subject: str
    body: str
    category: str

class CategoryOutput(BaseModel):
    category: str

class ResponseOutput(BaseModel):
    response_text: str

# --- Plantillas de Prompt para LangChain (mantener igual) ---
classification_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA especializado en clasificar correos electrónicos.
    Tu tarea es clasificar el siguiente correo electrónico en una de las siguientes categorías predefinidas:
    - Soporte Técnico
    - Ventas
    - Facturación
    - General
    - Devoluciones
    - Otro (si no encaja en ninguna categoría anterior)

    Responde ÚNICAMENTE con el nombre de la categoría. No añadas explicaciones, puntos, comas ni ningún otro texto."""),
    ("human", "Asunto: {subject}\n\nCuerpo: {body}")
])
classification_chain = classification_prompt | llm | StrOutputParser()

response_generation_prompt = ChatPromptTemplate.from_messages([
    ("system", """Eres un asistente de IA amable y servicial especializado en generar borradores de respuesta a correos electrónicos.
    Tu objetivo es crear una respuesta profesional y educada, adaptada a la categoría del correo.
    Asegúrate de que la respuesta sea concisa, clara y directa.
    No incluyas saludos ni despedidas genéricas ("Estimado", "Atentamente").
    Crea solo el cuerpo del mensaje."""),
    ("human", "Asunto del correo original: {subject}\n\nCuerpo del correo original: {body}\n\nCategoría: {category}")
])
response_generation_chain = response_generation_prompt | llm | StrOutputParser()

# --- Función para Limpiar y Normalizar Contenido (mantener igual) ---
def clean_text_content(text_content: str) -> str:
    if not text_content:
        return ""
    if not isinstance(text_content, str):
        return str(text_content)

    if '<' in text_content and '>' in text_content and len(text_content) > 50:
        print(f"WARNING: Se detectaron etiquetas HTML en lo que debería ser texto plano. "
            f"Intentando limpiar con BeautifulSoup: {text_content[:200]}...")
        soup = BeautifulSoup(text_content, 'html.parser')
        for script_or_style in soup(["script", "style"]):
            script_or_style.extract()
        text = soup.get_text(separator=' ', strip=True)
    else:
        text = text_content

    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text

# --- Endpoints de la API ---

@app.post("/classify_email/",
        summary="Clasifica un correo electrónico",
        response_description="Categoría del correo clasificado",
        response_model=CategoryOutput)
async def classify_email_endpoint(request: Request): # <--- ¡CAMBIO CLAVE PARA DEPURACIÓN! Recibimos el objeto Request
    """
    [DEPURACIÓN ACTIVA] Recibe una solicitud de correo para inspeccionar su contenido crudo
    y diagnosticar problemas de formato JSON.
    """
    try:
        # Lee el cuerpo de la solicitud en crudo
        raw_body = await request.body()
        raw_body_str = raw_body.decode('utf-8')

        print(f"\n--- DEBUG: CUERPO CRUDO RECIBIDO DESDE MAKE.COM ---\n{raw_body_str}\n--- FIN CUERPO CRUDO ---\n")

        # Intentar parsear el JSON y luego validar con Pydantic
        try:
            data = json.loads(raw_body_str) # Intenta convertir la cadena cruda a un diccionario Python
            print(f"--- DEBUG: JSON PARSEADO CORRECTAMENTE ---\n{json.dumps(data, indent=2)}\n--- FIN JSON PARSEADO ---\n")

            email_input = EmailInput(**data) # Intenta validar el diccionario con el modelo Pydantic
            print(f"DEBUG: Validación Pydantic exitosa. Asunto: '{email_input.subject}', Inicio del cuerpo: '{email_input.body[:200]}...'")

            # Si la validación es exitosa, se procede con la lógica original
            cleaned_body = clean_text_content(email_input.body)
            print(f"DEBUG: Cuerpo normalizado para clasificación: '{cleaned_body[:500]}...'")

            category = await classification_chain.ainvoke({"subject": email_input.subject, "body": cleaned_body})
            return {"category": category.strip()}

        except json.JSONDecodeError as e:
            # Captura específicamente errores de formato JSON
            print(f"ERROR: Fallo al decodificar JSON del cuerpo crudo. Error: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Formato JSON inválido recibido: {e}. Cuerpo crudo: {raw_body_str[:500]}..."
            )
        except ValidationError as e:
            # Captura errores de validación de Pydantic (ej. campos faltantes, tipos incorrectos)
            print(f"ERROR: Error de Validación Pydantic para los datos de entrada: {e.errors()}")
            # Intenta mostrar los datos parseados antes de la validación fallida
            input_preview = {}
            if 'subject' in data: input_preview['subject'] = data['subject']
            if 'body' in data: input_preview['body_preview'] = data['body'][:200]
            raise HTTPException(
                status_code=422,
                detail={"message": "Error de validación de datos de entrada.", "errors": e.errors(), "input_preview": input_preview}
            )

    except Exception as e:
        # Captura cualquier otro error inesperado que no sea de JSON o Pydantic
        print(f"ERROR: Error inesperado en classify_email_endpoint (modo depuración): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor durante la depuración de clasificación: {e}"
        )

# --- Endpoint para Generar Respuesta (mantener igual la última versión que te pasé) ---
@app.post("/generate_response/",
        summary="Genera una respuesta para un correo",
        response_description="Texto de la respuesta generada",
        response_model=ResponseOutput)
async def generate_response_endpoint(response_data: ResponseInput):
    """
    Recibe el asunto, el cuerpo (en texto plano) y la categoría de un correo
    para generar un borrador de respuesta.
    """
    try:
        print(f"DEBUG: Body recibido para respuesta (Pydantic parsed) TIPO: {type(response_data.body)}")
        print(f"DEBUG: Body recibido para respuesta (Pydantic parsed) INICIO: {response_data.body[:500]}...")

        cleaned_body = clean_text_content(response_data.body)
        print(f"DEBUG: Body normalizado para respuesta (después de la función) INICIO: {cleaned_body[:500]}...")

        response_text = await response_generation_chain.ainvoke({
            "subject": response_data.subject,
            "body": cleaned_body,
            "category": response_data.category
        })
        return {"response_text": response_text.strip()}

    except ValidationError as e:
        print(f"ERROR: Validación Pydantic fallida en /generate_response/: {e.errors()}")
        error_detail = {"subject": response_data.subject, "body_preview": response_data.body[:200], "category": response_data.category}
        raise HTTPException(
            status_code=422,
            detail={"message": "Error de validación de datos de entrada.", "errors": e.errors(), "input_preview": error_detail}
        )
    except Exception as e:
        print(f"ERROR: Error inesperado al generar la respuesta: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error interno del servidor durante la generación de respuesta: {e}. Asunto: {response_data.subject[:100]}"
        )

# --- Endpoint de Prueba (Health Check) ---
@app.get("/", summary="Verificar estado de la API")
async def read_root():
    """
    Endpoint simple para verificar que la API está funcionando correctamente.
    Retorna un mensaje de éxito.
    """
    return {"message": "API de automatización de correo con LangChain y Gemini funcionando correctamente."}