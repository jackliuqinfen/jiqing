import unittest
from pathlib import Path


class DocumentDeployContractTests(unittest.TestCase):
    def test_ocr_runtime_dependencies_are_exactly_pinned(self):
        requirements = (
            Path(__file__).resolve().parents[1] / "requirements-ocr.txt"
        ).read_text(encoding="utf-8").splitlines()

        self.assertTrue(requirements)
        self.assertTrue(all("==" in line for line in requirements if line.strip()))
        self.assertFalse(any(">" in line or "<" in line for line in requirements))

    def test_ocr_dependencies_are_verified_before_live_files_are_replaced(self):
        script = (
            Path(__file__).resolve().parents[2] / "deploy-shenjikanban.sh"
        ).read_text(encoding="utf-8")

        requirements = 'OCR_REQUIREMENTS="$WORK_DIR/server/requirements-ocr.txt"'
        import_check = 'print(\'OCR_IMPORT_OK\')'
        frontend_copy = 'cp -a "$WORK_DIR/dist/." "$FRONTEND_ROOT/"'
        server_copy = 'find "$WORK_DIR/server"'

        self.assertIn(requirements, script)
        self.assertIn(
            'OCR_VENV_ROOT="$OCR_VENV_BASE/$OCR_REQUIREMENTS_HASH"', script
        )
        self.assertLess(script.index(import_check), script.index(frontend_copy))
        self.assertLess(script.index(import_check), script.index(server_copy))

    def test_recognition_runtime_package_is_deployed_and_verified(self):
        script = (
            Path(__file__).resolve().parents[2] / "deploy-shenjikanban.sh"
        ).read_text(encoding="utf-8")

        package_copy = 'cp -a "$WORK_DIR/server/recognition/." "$API_ROOT/recognition/"'
        runtime_check = "recognition_service.py recognition_worker.py"
        package_check = "recognition/contracts.py recognition/registry.py"

        self.assertIn('mkdir -p "$API_ROOT/recognition"', script)
        self.assertIn(package_copy, script)
        self.assertIn(runtime_check, script)
        self.assertIn(package_check, script)

    def test_deploy_health_check_requires_a_live_recognition_worker(self):
        script = (
            Path(__file__).resolve().parents[2] / "deploy-shenjikanban.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('health = data.get("data", data)', script)
        self.assertIn('health.get("recognitionWorkerAlive") is not True', script)


if __name__ == "__main__":
    unittest.main()
