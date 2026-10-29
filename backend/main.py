from fastapi import FastAPI



app = FastAPI(title="API")



@app.get("/")
def health():
    return {"Status": "Ok!"}