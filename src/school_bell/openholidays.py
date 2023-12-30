#!/usr/bin/python3

# absolute imports
import json
import requests

# Relative imports
from .utils import to_date


__all__ = ['OpenHolidays']


class OpenHolidays(object):
    """Retrieve public and school holidays from OpenHolidays API.
    """

    def __init__(self, countryIsoCode: str = None, languageIsoCode: str = None,
                 subdivisionCode: str = None):
        """Initialize the Open Holidays API object
        """
        self.__countryIsoCode = countryIsoCode
        self.__languageIsoCode = languageIsoCode
        self.__subdivisionCode = subdivisionCode
        self.__swagger = self._get("swagger/v1/swagger.json")
        self.__is_holiday_request = None
        self.__is_holiday = False

    @property
    def countryIsoCode(self):
        """Returns the class countryIsoCode.
        """
        return self.__countryIsoCode

    @property
    def languageIsoCode(self):
        """Returns the class languageIsoCode.
        """
        return self.__languageIsoCode

    @property
    def subdivisionCode(self):
        """Returns the class subdivisionCode.
        """
        return self.__subdivisionCode

    @property
    def _swagger(self):
        """Returns the openapi swagger.
        """
        return self.__swagger

    def __str__(self):
        """Get the formatted openholidays api title.
        """
        return self.title

    @property
    def title(self):
        """Get the openholidays api title.
        """
        return self._swagger['info']['title']

    @property
    def description(self):
        """Get the openholidays api description.
        """
        return self._swagger['info']['description']

    @property
    def version(self):
        """Get the openholidays api version.
        """
        return self._swagger['info']['version']

    @property
    def base_url(self):
        """Returns the openholidays api base url.
        """
        return "https://openholidaysapi.org"

    def url(self, *args):
        """Returns the specific url.
        """
        return '/'.join([self.base_url, *args])

    def _get(self, path: str, *args, **kwargs) -> list:
        """Returns the parsed json object of the get request to the API.
        """
        parse_dates = kwargs.pop('parse_dates', True)
        data = json.loads(requests.get(self.url(path), *args, **kwargs).text)
        if parse_dates:
            _parse_holiday_dates(data)
        return data

    def publicHolidays(
        self, validFrom: str, validTo: str = None, countryIsoCode: str = None,
        languageIsoCode: str = None, subdivisionCode: str = None, **kwargs
    ) -> list:
        """Returns a list of public holidays for a given country

        Parameters
        ----------
        validFrom : `str`
            Start of the data range (format: %Y-%m-%d).

            _Example_: 2023-01-01

        validTo : `str`, optional
            End of the data range (format: %Y-%m-%d).
            Defaults to `validFrom`.

            _Example_: 2023-12-31

        countryIsoCode : `str`
            ISO 3166-1 code of the country (required).
            Defaults to the class countryIsoCode.

            _Example_: BE

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        subdivisionCode : `str`, optional
            Code of the subdivision or empty.
            Defaults to the class subdivisionCode.

            _Example_: NL-BE

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=countryIsoCode or self.countryIsoCode,
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            validFrom=str(validFrom),
            validTo=str(validTo or validFrom),
            subdivisionCode=subdivisionCode or self.subdivisionCode
        )
        return self._get('PublicHolidays', args, **kwargs)

    def publicHolidaysByDate(
        self, date: str, languageIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of public holidays from all countries
        for a given date

        Parameters
        ----------
        date : `str`
            Date of interest (format: %Y-%m-%d).

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            date=str(date),
        )
        return self._get('PublicHolidaysByDate', args, **kwargs)

    def schoolHolidays(
        self, validFrom: str, validTo: str = None, countryIsoCode: str = None,
        languageIsoCode: str = None, subdivisionCode: str = None, **kwargs
    ) -> list:
        """Returns a list of school holidays for a given country

        Parameters
        ----------
        validFrom : `str`
            Start of the data range (format: %Y-%m-%d).

            _Example_: 2023-01-01

        validTo : `str`, optional
            End of the data range (format: %Y-%m-%d).
            Defaults to `validFrom`.

            _Example_: 2023-12-31

        countryIsoCode : `str`
            ISO 3166-1 code of the country (required).
            Defaults to the class countryIsoCode.

            _Example_: BE

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        subdivisionCode : `str`, optional
            Code of the subdivision or empty.
            Defaults to the class subdivisionCode.

            _Example_: NL-BE

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=countryIsoCode or self.countryIsoCode,
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            validFrom=str(validFrom),
            validTo=str(validTo or validFrom),
            subdivisionCode=subdivisionCode or self.subdivisionCode
        )
        print(args)
        return self._get('SchoolHolidays', args, **kwargs)

    def schoolHolidaysByDate(
        self, date: str, languageIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of school holidays from all countries
        for a given date

        Parameters
        ----------
        date : `str`
            Date of interest (format: %Y-%m-%d).

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            date=str(date),
        )
        return self._get('SchoolHolidaysByDate', args, **kwargs)

    def holidays(
        self, validFrom: str, validTo: str = None, countryIsoCode: str = None,
        languageIsoCode: str = None, subdivisionCode: str = None, **kwargs
    ) -> list:
        """Returns a list of public and school holidays for a given country

        Parameters
        ----------
        validFrom : `str`
            Start of the data range (format: %Y-%m-%d).

            _Example_: 2023-01-01

        validTo : `str`, optional
            End of the data range (format: %Y-%m-%d).
            Defaults to `validFrom`.

            _Example_: 2023-12-31

        countryIsoCode : `str`
            ISO 3166-1 code of the country (required).
            Defaults to the class countryIsoCode.

            _Example_: BE

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        subdivisionCode : `str`, optional
            Code of the subdivision or empty.
            Defaults to the class subdivisionCode.

            _Example_: NL-BE

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=countryIsoCode or self.countryIsoCode,
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            validFrom=str(validFrom),
            validTo=str(validTo or validFrom),
            subdivisionCode=subdivisionCode or self.subdivisionCode
        )
        return (
            self._get('SchoolHolidays', args, **kwargs) +
            self._get('PublicHolidays', args, **kwargs)
        )

    def holidaysByDate(
        self, date: str, languageIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of public and school holidays from all countries
        for a given date

        Parameters
        ----------
        date : `str`
            Date of interest (format: %Y-%m-%d).

            _Example_: 2023-12-25

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=languageIsoCode or self.__languageIsoCode,
            date=str(date),
        )
        return (
            self._get('PublicHolidaysByDate', args, **kwargs) +
            self._get('SchoolHolidaysByDate', args, **kwargs)
        )

    def countries(
        self, languageIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of all supported countries

        Parameters
        ----------
        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            languageIsoCode=languageIsoCode or self.languageIsoCode
        )
        return self._get('Countries', args, **kwargs)

    def languages(
        self, countryIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of all used languages

        Parameters
        ----------
        countryIsoCode : `str`, optional
            ISO 3166-1 code of the country or empty.
            Defaults to the class countryIsoCode.

            _Example_: BE

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=countryIsoCode or self.countryIsoCode
        )
        return self._get('Languages', args, **kwargs)

    def subdivisions(
        self, countryIsoCode: str = None, languageIsoCode: str = None, **kwargs
    ) -> list:
        """Returns a list of relevant subdivisions for a supported country

        Parameters
        ----------
        countryIsoCode : `str`
            ISO 3166-1 code of the country (required).
            Defaults to the class countryIsoCode.

            _Example_: BE

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """
        args = dict(
            countryIsoCode=countryIsoCode or self.countryIsoCode,
            languageIsoCode=languageIsoCode or self.languageIsoCode
        )
        return self._get('Subdivisions', args, **kwargs)

    def isHoliday(
        self, date: str, countryIsoCode: str = None,
        languageIsoCode: str = None, subdivisionCode: str = None,
        **kwargs
    ) -> list:
        """Returns True if the date is either a public or school holiday.
        Returns False for any input error or a timeout.

        Parameters
        ----------
        date : `str`
            Start of the data range (format: %Y-%m-%d).

            _Example_: 2023-12-25

        countryIsoCode : `str`
            ISO 3166-1 code of the country (required).
            Defaults to the class countryIsoCode.

            _Example_: BE

        languageIsoCode : `str`, optional
            ISO-639-1 code of a language or empty.
            Defaults to the class languageIsoCode.

            _Example_: NL

        subdivisionCode : `str`, optional
            Code of the subdivision or empty.
            Defaults to the class subdivisionCode.

            _Example_: NL-BE

        **kwargs :
            Parameters passed to :func:`requests.get`.
        """

        args = dict(
            validFrom=str(date),
            countryIsoCode=countryIsoCode or self.countryIsoCode,
            languageIsoCode=languageIsoCode or self.languageIsoCode,
            subdivisionCode=subdivisionCode or self.subdivisionCode,
            **kwargs
        )

        if self.__is_holiday_request == json.dumps(args):
            return self.__is_holiday

        holiday = self.holidays(**args)

        holiday = False if not holiday or 'status' in holiday else True

        self.__is_holiday_request = json.dumps(args)
        self.__is_holiday = holiday

        return holiday

    @property
    def _isHoliday(self):
        """Internal function
        """
        return self.__is_holiday

    @property
    def _isHolidayRequest(self):
        """Internal function
        """
        return self.__is_holiday_request


def _parse_holiday_dates(holidays: list):
    """Parse the holidays list and inplace convert dates to `datetime.date`.
    """
    if not isinstance(holidays, list):
        return
    for i in range(len(holidays)):
        if 'startDate' in holidays[i]:
            holidays[i]['startDate'] = to_date(holidays[i]['startDate'])
        if 'endDate' in holidays[i]:
            holidays[i]['endDate'] = to_date(holidays[i]['endDate'])
