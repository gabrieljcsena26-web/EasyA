from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get('/')
def root():
    return {'ok': True}

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=9000, log_level='debug')
