from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Integer, String, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.enums import JobStatus, JobType


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checkpoint_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    carbon_used_g: Mapped[float] = mapped_column(Float, default=0.0)
    energy_used_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    baseline_carbon_estimate_g: Mapped[float] = mapped_column(Float, default=0.0)
    pause_count: Mapped[int] = mapped_column(Integer, default=0)
    current_epoch: Mapped[int] = mapped_column(Integer, default=0)
    performance_target: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_epochs: Mapped[int] = mapped_column(Integer, default=2)
    total_duration_hours: Mapped[float] = mapped_column(Float, default=0.0)


class JobTypeProfileRow(Base):
    __tablename__ = "job_type_profiles"

    job_type: Mapped[JobType] = mapped_column(Enum(JobType), primary_key=True)
    expected_power_draw_kw: Mapped[float] = mapped_column(Float, nullable=False)
    expected_duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)


# Conservative placeholder seed defaults (Q4) — refined after first completed run per type.
DEFAULT_PROFILES: dict[JobType, tuple[float, float]] = {
    JobType.RESNET50_CIFAR: (0.15, 0.25),  # ~150W, ~15 min for 1-2 epochs on subset
    JobType.BERT_IMDB: (0.12, 0.20),       # ~120W, ~12 min for 1 epoch on 200 rows
    JobType.SIMULATED: (0.05, 0.05),        # fast simulated job for tests
}


def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.close()


class PersistentJobStore:
    def __init__(self, database_url: str) -> None:
        self._engine = create_async_engine(database_url, echo=False)
        event.listen(self._engine.sync_engine, "connect", _set_sqlite_pragma)
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self) -> None:
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await self._seed_profiles()

    async def _seed_profiles(self) -> None:
        async with self._session_factory() as session:
            for job_type, (power_kw, duration_h) in DEFAULT_PROFILES.items():
                existing = await session.get(JobTypeProfileRow, job_type)
                if existing is None:
                    session.add(
                        JobTypeProfileRow(
                            job_type=job_type,
                            expected_power_draw_kw=power_kw,
                            expected_duration_hours=duration_h,
                            sample_count=0,
                        )
                    )
            await session.commit()

    async def create_job(
        self,
        name: str,
        job_type: JobType,
        priority: int,
        deadline: Optional[datetime],
        performance_target: Optional[int],
        total_epochs: int,
        baseline_carbon_estimate_g: float,
    ) -> JobRow:
        async with self._session_factory() as session:
            job = JobRow(
                name=name,
                job_type=job_type,
                status=JobStatus.QUEUED,
                priority=priority,
                deadline=deadline,
                performance_target=performance_target,
                total_epochs=total_epochs,
                baseline_carbon_estimate_g=baseline_carbon_estimate_g,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def get_job(self, job_id: int) -> Optional[JobRow]:
        async with self._session_factory() as session:
            return await session.get(JobRow, job_id)

    async def list_jobs(self) -> list[JobRow]:
        async with self._session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(select(JobRow).order_by(JobRow.id))
            return list(result.scalars().all())

    async def update_job(self, job_id: int, **fields) -> Optional[JobRow]:
        async with self._session_factory() as session:
            job = await session.get(JobRow, job_id)
            if job is None:
                return None
            for key, value in fields.items():
                setattr(job, key, value)
            await session.commit()
            await session.refresh(job)
            return job

    async def get_jobs_by_status(self, status: JobStatus) -> list[JobRow]:
        async with self._session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(JobRow).where(JobRow.status == status).order_by(JobRow.priority.desc())
            )
            return list(result.scalars().all())

    async def get_profile(self, job_type: JobType) -> Optional[JobTypeProfileRow]:
        async with self._session_factory() as session:
            return await session.get(JobTypeProfileRow, job_type)

    async def update_profile(
        self,
        job_type: JobType,
        expected_power_draw_kw: float,
        expected_duration_hours: float,
        sample_count: int,
    ) -> JobTypeProfileRow:
        async with self._session_factory() as session:
            profile = await session.get(JobTypeProfileRow, job_type)
            if profile is None:
                profile = JobTypeProfileRow(
                    job_type=job_type,
                    expected_power_draw_kw=expected_power_draw_kw,
                    expected_duration_hours=expected_duration_hours,
                    sample_count=sample_count,
                )
                session.add(profile)
            else:
                profile.expected_power_draw_kw = expected_power_draw_kw
                profile.expected_duration_hours = expected_duration_hours
                profile.sample_count = sample_count
            await session.commit()
            await session.refresh(profile)
            return profile

    async def count_by_status(self) -> dict[str, int]:
        jobs = await self.list_jobs()
        counts: dict[str, int] = {}
        for job in jobs:
            counts[job.status.value] = counts.get(job.status.value, 0) + 1
        return counts

    async def total_carbon_saved(self) -> float:
        jobs = await self.list_jobs()
        return sum(
            max(0.0, j.baseline_carbon_estimate_g - j.carbon_used_g)
            for j in jobs
            if j.status == JobStatus.COMPLETED
        )

    async def dispose(self) -> None:
        await self._engine.dispose()
