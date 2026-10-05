import asyncio
from app.db.session import engine, Base
from app.db.models import (
    DeviceModel, SessionModel, SensorSnapshotModel, ExpertRunModel,
    EvidenceModel, EventModel, LocationModel, DeviceHealthModel
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    asyncio.run(init_db())
