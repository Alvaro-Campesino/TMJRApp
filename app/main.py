import routers.usuarias as usr
import routers.premisas as pre
import routers.aventuras as avn
import routers.roles as rls
import routers.sesiones as ses
import routers.participaciones as par
import routers.esperas as esp
from fastapi import FastAPI

app = FastAPI()

app.include_router(usr.router)
app.include_router(pre.router)
app.include_router(avn.router)
app.include_router(rls.router)
app.include_router(ses.router)
app.include_router(par.router)
app.include_router(esp.router)

# if __name__ == 'main':
#     uvicorn.run(app, log_level="trace")
