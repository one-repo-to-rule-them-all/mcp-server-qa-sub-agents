# Media Collection Tracker - Testing Setup Guide

## 📋 Quick Setup Instructions

Follow these steps to add automated testing to your repository:

### Step 1: Create Directory Structure

```bash
cd /path/to/media-collection-tracker

# Create test directories
mkdir -p .github/workflows
mkdir -p tests/e2e
mkdir -p tests/unit
```

### Step 2: Add GitHub Actions Workflow

Copy the `qa_testing.yml` file to your repository:

```bash
# Place the workflow file
cp qa_testing.yml .github/workflows/qa_testing.yml
```

**File location**: `.github/workflows/qa_testing.yml`

This workflow will:
- ✅ Run automatically on every push to `main` or `develop`
- ✅ Run on every pull request
- ✅ Execute unit tests with coverage
- ✅ Execute E2E tests with Playwright
- ✅ Upload coverage reports
- ✅ Generate HTML test reports

### Step 3: Add Pytest Configuration

```bash
# Copy pytest configuration to repository root
cp pytest.ini .
```

**File location**: `pytest.ini` (root of repository)

### Step 4: Add E2E Test Files

```bash
# Copy E2E test configuration
cp conftest_e2e.py tests/e2e/conftest.py

# Copy E2E test examples
cp test_media_tracker_e2e.py tests/e2e/test_media_tracker_e2e.py
```

### Step 5: Update Requirements

Add these testing dependencies to your `requirements.txt` or create a `requirements-dev.txt`:

```txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-html>=3.2.0
playwright>=1.40.0
```

### Step 6: Install Playwright Browsers (Local Only)

```bash
# Install Playwright browsers for local testing
playwright install chromium
```

### Step 7: Customize the Tests

#### For E2E Tests (`tests/e2e/test_media_tracker_e2e.py`):

Replace the commented placeholders with actual selectors from your application:

```python
# Example: Instead of this comment
# page.click("button:has-text('Add Media')")

# Add actual code based on your HTML
page.click("#add-media-button")
```

To find the right selectors:
1. Open your app in a browser
2. Right-click an element → Inspect
3. Use the element's ID, class, or text

#### For Unit Tests:

Create unit test files in `tests/unit/` for your Python modules:

```python
# tests/unit/test_models.py
import pytest
from your_app import models

def test_media_model_creation():
    media = models.Media(
        title="Test Movie",
        type="movie",
        year=2024
    )
    assert media.title == "Test Movie"
    assert media.type == "movie"
```

### Step 8: Test Locally

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only E2E tests (make sure your app is running on localhost:8000)
pytest tests/e2e/

# Run with coverage
pytest --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Step 9: Commit and Push

```bash
git add .github/workflows/qa_testing.yml
git add pytest.ini
git add tests/
git add requirements-dev.txt  # if you created this

git commit -m "Add automated testing infrastructure"
git push origin main
```

### Step 10: Verify GitHub Actions

1. Go to your repository on GitHub
2. Click the "Actions" tab
3. You should see "Autonomous QA Testing" workflow
4. The workflow will run automatically on your next push or PR

## 🎯 Understanding the Test Structure

```
media-collection-tracker/
├── .github/
│   └── workflows/
│       └── qa_testing.yml          # GitHub Actions workflow
├── tests/
│   ├── e2e/
│   │   ├── conftest.py             # Playwright configuration
│   │   └── test_media_tracker_e2e.py  # E2E tests
│   └── unit/
│       └── test_*.py               # Unit tests (you create these)
├── pytest.ini                      # Pytest configuration
└── requirements-dev.txt            # Testing dependencies
```

## 🔧 Customization Guide

### Customizing E2E Tests

1. **Find your page elements**:
   ```bash
   # Start your app
   python app.py  # or however you run it
   
   # Open browser to http://localhost:8000
   # Inspect elements to find selectors
   ```

2. **Common selector patterns**:
   ```python
   # By ID
   page.click("#button-id")
   
   # By class
   page.click(".btn-primary")
   
   # By text
   page.click("button:has-text('Submit')")
   
   # By attribute
   page.click("button[name='submit']")
   ```

3. **Update base_url** if your app runs on a different port:
   ```python
   # In tests/e2e/conftest.py
   @pytest.fixture
   def base_url():
       return "http://localhost:YOUR_PORT"
   ```

### Adding Unit Tests

Create a test file for each module:

```python
# tests/unit/test_database.py
import pytest
from your_app import database

def test_database_connection():
    """Test database connects successfully."""
    db = database.connect()
    assert db is not None

def test_add_media_item():
    """Test adding a media item to database."""
    result = database.add_media("Test Movie", "movie")
    assert result.id is not None
    assert result.title == "Test Movie"
```

### Adjusting Coverage Thresholds

Edit `pytest.ini` to add minimum coverage requirements:

```ini
[coverage:report]
fail_under = 80  # Fail if coverage is below 80%
```

## 🐛 Troubleshooting

### Tests fail with "element not found"
- Your app might not be running
- Selectors might have changed
- Add wait conditions: `page.wait_for_selector("#element")`

### GitHub Actions fails but local tests pass
- Check if all dependencies are in `requirements.txt`
- Verify Python version matches in workflow (currently 3.11)
- Check action logs for specific error messages

### Coverage reports not generating
- Ensure `pytest-cov` is installed
- Check that source paths are correct in `pytest.ini`

## 📊 What You Get

Once set up, every push will:
1. ✅ Run all tests automatically
2. ✅ Generate coverage reports
3. ✅ Show test results in PR checks
4. ✅ Upload HTML reports as artifacts
5. ✅ Fail the build if tests fail (you can adjust this)

## 🎓 Next Steps

1. **Start with unit tests**: Test your core logic first
2. **Add E2E tests gradually**: One user flow at a time
3. **Increase coverage**: Aim for 80%+ coverage
4. **Review PR checks**: Use them to maintain quality

Need help customizing tests for your specific application? Let me know what features you want to test!