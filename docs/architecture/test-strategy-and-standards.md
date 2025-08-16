# Test Strategy and Standards

## Testing Philosophy
- **Approach:** Test critical paths thoroughly, skip trivial getters/setters
- **Coverage Goals:** 80% for core modules, 100% for risk management ✅ **ACHIEVED: 87% overall coverage**
- **Test Pyramid:** 70% unit, 20% integration, 10% end-to-end
- **Test Count:** 179+ comprehensive tests across all modules

## Test Types and Organization

### Unit Tests ✅ **ACHIEVED**
- **Framework:** pytest 8.3.0
- **File Convention:** `test_[module_name].py`
- **Location:** `tests/` subdirectory in each module
- **Mocking Library:** unittest.mock + pytest fixtures
- **Coverage Requirement:** 80% minimum ✅ **87% achieved**
- **Test Modules:**
  - **CLI Tests:** 65+ tests across 7 command modules
  - **Model Tests:** 150+ tests for data validation and schema
  - **Utility Tests:** AsyncIO and file watching components
  - **Integration Tests:** End-to-end workflow validation

**AI Agent Requirements:** ✅ **IMPLEMENTED**
- Generate tests for all public methods ✅
- Cover edge cases and error conditions ✅
- Follow AAA pattern (Arrange, Act, Assert) ✅
- Mock all external dependencies ✅
- **NEW:** Comprehensive CLI command testing with Click framework
- **NEW:** AsyncIO component testing with proper event loop handling
- **NEW:** File watching system testing with temporary directories

### Integration Tests
- **Scope:** IBKR connection, file I/O, complete workflows
- **Location:** `tests/integration/`
- **Test Infrastructure:**
  - **IBKR API:** Paper trading account for integration tests
  - **File System:** Temp directories with cleanup
  - **Time:** freezegun for time-dependent tests

## Test Data Management
- **Strategy:** Fixtures for common test data
- **Fixtures:** `tests/conftest.py` for shared fixtures
- **Factories:** pydantic model factories for test objects
- **Cleanup:** Automatic cleanup with pytest fixtures

## Continuous Testing
- **CI Integration:** GitHub Actions on every push
- **Performance Tests:** Not required for MVP
- **Security Tests:** dependency scanning with pip-audit
