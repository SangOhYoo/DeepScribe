import uvicorn
import os

if __name__ == "__main__":
    # 백엔드 서버는 기본적으로 8000번 포트에서 동작합니다.
    # React Vite 개발 서버와 교차 출처 리소스 공유(CORS)를 연동합니다.
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8002,
        reload=True
    )
