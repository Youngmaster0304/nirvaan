import uvicorn
import sys
sys.path.insert(0, r'C:\Users\Abhinav\sih-railways')
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
