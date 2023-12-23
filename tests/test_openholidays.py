# content of test_openholidays.py
from datetime import date
from school_bell.openholidays import OpenHolidays

countryIsoCode = 'BE'
languageIsoCode = 'NL'
subdivisionCode = 'NL-BE'

startDate = date.today().strftime("%Y-01-01")
endDate = date.today().strftime("%Y-01-10")

oh = OpenHolidays(countryIsoCode, languageIsoCode, subdivisionCode)

def test_countryIsoCode():
    assert oh.countryIsoCode == countryIsoCode

def test_languageIsoCode():
    assert oh.languageIsoCode == languageIsoCode

def test_subdivisionCode():
    assert oh.subdivisionCode == subdivisionCode

def test_url():
    url = "https://openholidaysapi.org/swagger/v1/swagger.json"
    assert oh.url("swagger/v1/swagger.json") == url

def test_title():
    assert isinstance(oh.title, str)

def test_description():
    assert isinstance(oh.description, str)

def test_version():
    assert isinstance(oh.version, str)

def test_isHoliday_true():
    assert oh.isHoliday(startDate) == True

def test_isHoliday():
    assert oh.isHoliday(endDate) == False

def test_publicHolidays():
    r = oh.publicHolidays(startDate, endDate)
    assert r[0]['startDate'] == startDate
    assert r[0]['endDate'] == startDate
    assert r[0]['type'] == "Public"
    assert r[0]['nationwide'] == True

def test_publicHolidaysByDate():
    r = oh.publicHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "Public"

def test_schoolHolidays():
    r = oh.schoolHolidays(startDate, endDate)
    assert r[0]['type'] == "School"

def test_schoolHolidaysByDate():
    r = oh.schoolHolidaysByDate(startDate, languageIsoCode)
    assert r[0]['type'] == "School"
