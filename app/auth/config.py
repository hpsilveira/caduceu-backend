import os

from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 horas de expediente na SESAP
# Assina os JWTs. Não há default no código de propósito: um valor embutido no repositório
# permite forjar tokens para qualquer usuário e setor. Obrigatória em AUTH_SECRET_KEY.
SECRET_KEY = os.environ["AUTH_SECRET_KEY"]
ALGORITHM = "HS256"