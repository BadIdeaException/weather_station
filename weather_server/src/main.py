import asyncio
import uvicorn
from core.rest import REST
from core.data_engine import DataEngine

async def main():
    with DataEngine() as engine:
        rest = REST(engine)
        http = uvicorn.Server(uvicorn.Config(
            rest.api,
            host="0.0.0.0",
            port=80,
        ))

        async with asyncio.TaskGroup() as tg:
            tg.create_task(engine.run())
            tg.create_task(http.serve())



if __name__ == '__main__':
    asyncio.run(main())