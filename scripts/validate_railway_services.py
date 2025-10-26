"""
Railway Services Validation Script
Tests connections to all Railway services:
- Prefect Server + Postgres-XOqe (metadata DB)
- pgvector Postgres (application DB)
- Redis
- Kafka
- MinIO/Bucket

Usage:
    python scripts/validate_railway_services.py
"""

import asyncio
import sys
from typing import Dict, Any
from datetime import datetime
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class ServiceValidator:
    """Validates Railway service connections"""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.load_env()

    def load_env(self):
        """Load production environment variables"""
        env_file = Path(__file__).parent.parent / ".env.production"
        if not env_file.exists():
            print("⚠️  .env.production not found, using environment variables")
            return

        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Skip variables that reference other env vars
                    if not value.startswith('${'):
                        os.environ[key] = value

    def log_test(self, service: str, status: str, message: str, details: dict = None):
        """Log test result"""
        emoji = "✅" if status == "success" else "❌" if status == "error" else "⚠️"
        print(f"{emoji} {service}: {message}")

        self.results[service] = {
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }

    async def test_prefect_metadata_db(self) -> bool:
        """Test Prefect metadata database (Postgres-XOqe)"""
        print("\n🔍 Testing Prefect Metadata DB (Postgres-XOqe)...")

        try:
            import asyncpg

            db_url = os.getenv("PREFECT_API_DATABASE_CONNECTION_URL", "")
            if not db_url:
                self.log_test("Prefect Metadata DB", "error",
                              "Missing PREFECT_API_DATABASE_CONNECTION_URL")
                return False

            # Parse asyncpg URL
            url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            conn = await asyncpg.connect(url)

            # Test basic query
            version = await conn.fetchval("SELECT version();")

            # Check Prefect tables
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('flow', 'flow_run', 'task_run', 'deployment')
                ORDER BY table_name;
            """
            tables = await conn.fetch(tables_query)
            table_names = [row['table_name'] for row in tables]

            # Count flow runs
            flow_run_count = await conn.fetchval("SELECT COUNT(*) FROM flow_run;")

            await conn.close()

            self.log_test(
                "Prefect Metadata DB",
                "success",
                f"Connected successfully - {len(table_names)} Prefect tables found",
                {
                    "database": "railway",
                    "host": "maglev.proxy.rlwy.net:51894",
                    "prefect_tables": table_names,
                    "flow_runs": flow_run_count,
                    "postgres_version": version[:50]
                }
            )
            return True

        except ImportError:
            self.log_test("Prefect Metadata DB", "error",
                          "asyncpg not installed: pip install asyncpg")
            return False
        except Exception as e:
            self.log_test("Prefect Metadata DB", "error",
                          f"Connection failed: {str(e)}")
            return False

    async def test_pgvector_db(self) -> bool:
        """Test pgvector application database"""
        print("\n🔍 Testing pgvector Application DB...")

        try:
            import asyncpg

            db_url = os.getenv("DATABASE_PUBLIC_URL", "")
            if not db_url:
                self.log_test("pgvector DB", "error",
                              "Missing DATABASE_PUBLIC_URL")
                return False

            conn = await asyncpg.connect(db_url)

            # Test basic query
            version = await conn.fetchval("SELECT version();")

            # Check pgvector extension
            pgvector_query = """
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname = 'vector';
            """
            pgvector = await conn.fetch(pgvector_query)
            has_pgvector = len(pgvector) > 0

            # Check our application tables
            tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('bills', 'politicians', 'fetch_logs', 'alembic_version')
                ORDER BY table_name;
            """
            tables = await conn.fetch(tables_query)
            table_names = [row['table_name'] for row in tables]

            # Count bills
            bill_count = 0
            if 'bills' in table_names:
                bill_count = await conn.fetchval("SELECT COUNT(*) FROM bills;")

            await conn.close()

            self.log_test(
                "pgvector DB",
                "success",
                f"Connected successfully - pgvector: {has_pgvector}, {len(table_names)} tables",
                {
                    "database": "railway",
                    "host": "shortline.proxy.rlwy.net:21723",
                    "pgvector_enabled": has_pgvector,
                    "pgvector_version": pgvector[0]['extversion'] if pgvector else None,
                    "application_tables": table_names,
                    "bill_count": bill_count,
                    "postgres_version": version[:50]
                }
            )
            return True

        except ImportError:
            self.log_test("pgvector DB", "error",
                          "asyncpg not installed: pip install asyncpg")
            return False
        except Exception as e:
            self.log_test("pgvector DB", "error",
                          f"Connection failed: {str(e)}")
            return False

    async def test_redis(self) -> bool:
        """Test Redis connection"""
        print("\n🔍 Testing Redis...")

        try:
            import redis.asyncio as aioredis

            redis_url = os.getenv("REDIS_URL", "")
            if not redis_url:
                self.log_test("Redis", "error", "Missing REDIS_URL")
                return False

            client = await aioredis.from_url(redis_url, decode_responses=True)

            # Test ping
            pong = await client.ping()

            # Test set/get
            test_key = "validation_test"
            await client.set(test_key, "test_value", ex=10)
            test_value = await client.get(test_key)
            await client.delete(test_key)

            # Get Redis info
            info = await client.info()

            await client.close()

            self.log_test(
                "Redis",
                "success",
                f"Connected successfully - version {info.get('redis_version', 'unknown')}",
                {
                    "host": "nozomi.proxy.rlwy.net:10324",
                    "redis_version": info.get('redis_version'),
                    "used_memory_human": info.get('used_memory_human'),
                    "connected_clients": info.get('connected_clients'),
                    "uptime_days": info.get('uptime_in_days'),
                    "test_set_get": test_value == "test_value"
                }
            )
            return True

        except ImportError:
            self.log_test("Redis", "error",
                          "redis not installed: pip install redis")
            return False
        except Exception as e:
            self.log_test("Redis", "error", f"Connection failed: {str(e)}")
            return False

    async def test_kafka(self) -> bool:
        """Test Kafka connection"""
        print("\n🔍 Testing Kafka...")

        try:
            from aiokafka import AIOKafkaProducer
            from aiokafka.admin import AIOKafkaAdminClient, NewTopic

            kafka_url = os.getenv("KAFKA_PUBLIC_URL", "")
            if not kafka_url:
                self.log_test("Kafka", "error", "Missing KAFKA_PUBLIC_URL")
                return False

            # Create admin client
            admin = AIOKafkaAdminClient(
                bootstrap_servers=kafka_url,
                request_timeout_ms=10000
            )

            try:
                await admin.start()

                # Get cluster metadata (using private API as public one may vary by version)
                cluster = admin._client.cluster
                topics = list(cluster.topics())
                brokers = cluster.brokers()

                await admin.close()

                self.log_test(
                    "Kafka",
                    "success",
                    f"Connected successfully - {len(topics)} topics found",
                    {
                        "host": kafka_url,
                        # First 10 topics
                        "topics": topics[:10] if topics else [],
                        "brokers": len(brokers)
                    }
                )
                return True
            except Exception as e:
                await admin.close()
                raise e

        except ImportError:
            self.log_test("Kafka", "warning",
                          "aiokafka not installed: pip install aiokafka")
            return False
        except Exception as e:
            self.log_test("Kafka", "error", f"Connection failed: {str(e)}")
            return False

    async def test_minio(self) -> bool:
        """Test MinIO/S3 bucket connection"""
        print("\n🔍 Testing MinIO/Bucket...")

        try:
            from minio import Minio

            endpoint = os.getenv("MINIO_PRIVATE_ENDPOINT", "")
            access_key = os.getenv("MINIO_ROOT_USER", "")
            secret_key = os.getenv("MINIO_ROOT_PASSWORD", "")
            secure = os.getenv("MINIO_SECURE", "true").lower() == "true"

            if not all([endpoint, access_key, secret_key]):
                self.log_test(
                    "MinIO",
                    "error",
                    "Missing MINIO credentials (MINIO_PRIVATE_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD)",
                )
                return False

            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )

            # List buckets
            buckets = client.list_buckets()
            bucket_names = [b.name for b in buckets]

            # Check configured buckets
            expected_buckets = [
                os.getenv("MINIO_BUCKET_RAW", "parl-raw-prod"),
                os.getenv("MINIO_BUCKET_PROCESSED", "parl-processed-prod"),
                os.getenv("MINIO_BUCKET_BACKUPS", "backups-prod")
            ]

            missing_buckets = [
                b for b in expected_buckets if b not in bucket_names]

            self.log_test(
                "MinIO",
                "success" if not missing_buckets else "warning",
                f"Connected - {len(bucket_names)} buckets found" +
                (f", missing: {missing_buckets}" if missing_buckets else ""),
                {
                    "endpoint": endpoint,
                    "buckets": bucket_names,
                    "expected_buckets": expected_buckets,
                    "missing_buckets": missing_buckets
                }
            )
            return True

        except ImportError:
            self.log_test("MinIO", "error",
                          "minio not installed: pip install minio")
            return False
        except Exception as e:
            self.log_test("MinIO", "error", f"Connection failed: {str(e)}")
            return False

    async def test_prefect_server(self) -> bool:
        """Test Prefect server API"""
        print("\n🔍 Testing Prefect Server API...")

        try:
            import httpx

            api_url = os.getenv("PREFECT_API_URL", "")
            if not api_url:
                self.log_test("Prefect Server", "error",
                              "Missing PREFECT_API_URL")
                return False

            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test health endpoint
                health_url = api_url.replace("/api", "/health")
                response = await client.get(health_url)

                if response.status_code == 200:
                    # Try to get flow runs
                    flows_response = await client.post(
                        f"{api_url}/flow_runs/filter",
                        json={"limit": 1}
                    )

                    self.log_test(
                        "Prefect Server",
                        "success",
                        "API responding successfully",
                        {
                            "api_url": api_url,
                            "ui_url": os.getenv("PREFECT_UI_URL"),
                            "health_status": response.status_code,
                            "flows_accessible": flows_response.status_code == 200
                        }
                    )
                    return True
                else:
                    self.log_test("Prefect Server", "error",
                                  f"Health check failed: {response.status_code}")
                    return False

        except ImportError:
            self.log_test("Prefect Server", "error",
                          "httpx not installed: pip install httpx")
            return False
        except Exception as e:
            self.log_test("Prefect Server", "error",
                          f"Connection failed: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all validation tests"""
        print("=" * 80)
        print("🚀 Railway Services Validation")
        print("=" * 80)

        tests = [
            ("Prefect Server API", self.test_prefect_server),
            ("Prefect Metadata DB", self.test_prefect_metadata_db),
            ("pgvector Application DB", self.test_pgvector_db),
            ("Redis Cache", self.test_redis),
            ("Kafka Stream", self.test_kafka),
            ("MinIO/Bucket Storage", self.test_minio),
        ]

        success_count = 0
        warning_count = 0
        error_count = 0

        for name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    success_count += 1
            except Exception as e:
                print(f"❌ {name}: Unexpected error - {str(e)}")
                error_count += 1

        # Count statuses
        for result in self.results.values():
            if result["status"] == "warning":
                warning_count += 1
            elif result["status"] == "error":
                error_count += 1

        # Print summary
        print("\n" + "=" * 80)
        print("📊 Validation Summary")
        print("=" * 80)
        print(f"✅ Success: {success_count}")
        print(f"⚠️  Warning: {warning_count}")
        print(f"❌ Error: {error_count}")
        print(f"📊 Total: {len(tests)}")

        if success_count == len(tests):
            print("\n🎉 All services validated successfully!")
            return True
        elif error_count == 0:
            print("\n✅ All services accessible (some warnings)")
            return True
        else:
            print(f"\n⚠️  {error_count} service(s) failed validation")
            return False

    def print_details(self):
        """Print detailed results"""
        print("\n" + "=" * 80)
        print("📋 Detailed Results")
        print("=" * 80)

        for service, result in self.results.items():
            print(f"\n{service}:")
            print(f"  Status: {result['status']}")
            print(f"  Message: {result['message']}")
            if result.get('details'):
                print("  Details:")
                for key, value in result['details'].items():
                    print(f"    {key}: {value}")


async def main():
    """Main validation function"""
    validator = ServiceValidator()
    success = await validator.run_all_tests()
    validator.print_details()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
