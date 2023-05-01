"""
Class for address dataframe

Contains common functions for cleaning and geocoding.
"""
import pandas as pd
import os
import re
import requests
import json
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from geopy.exc import GeocoderUnavailable
from geopy.geocoders import Nominatim
from time import time

load_dotenv()


class AddressFrame:
    """
    Essentially a Pandas DataFrame with useful methods for geocoding.

    Parameters
    -------
    frame: pd.DataFrame
    add_col: str
        Column name of address data in frame.
    city_col: str
        Column name of city data in frame.
    state_col: str
        Column name of state data in frame.
    zip_col: str
        Column name of postalcode data in frame.
    state_filter: str | list, default None
        Keeps only geo results of states in state_filter. If None all geo results are kept.
        Useful when Nominatim server only has select states. If an address is in a state outside the server data
            then sometimes Nominatim will find the given address in the wrong state.
    Returns
    -------

    Raises
    ------
    requests.exceptions.ConnectionError
        _description_
    """

    NOM_URL = os.getenv('NOM_URL')
    # Initialize Nominatim
    if NOM_URL is None:
        print('Please create .env file with NOM_URL or set with AddressFrame.set_geocoder_url method')
    nom = Nominatim(domain=NOM_URL, scheme='http')

    def __init__(self, frame: pd.DataFrame, add_col: str, city_col: str, state_col: str, zip_col: str,
                 state_filter=None, keep_temp_cols=True):
        self.frame = frame
        self.add_col = add_col
        self.city_col = city_col
        self.state_col = state_col
        self.zip_col = zip_col
        self.state_filter = state_filter

    def verify_col(self, column):
        if not isinstance(column, str):
            print(f'{column} should be of type: str')
            return False
        elif not column in self.frame.columns:
            print(f'{column} not in AddressFrame columns.')
            return False
        return True

    def clean_streets(self, rplc_abbrvs=True):
        if self.verify_col(self.add_col):
            self.__setattr__('temp_add_field', 'cleaned_add_field')
            self.convert_field_to_str(self.add_col)
            self.frame[self.temp_add_field] = self.frame[self.add_col].apply(
                self._shorten_streets)
            if rplc_abbrvs:
                self.frame[self.temp_add_field] = self.frame[self.temp_add_field].apply(
                    self._street_cleaner)
        else:
            print('Streets will not be cleaned...')
        return self

    def clean_zips(self):
        if self.verify_col(self.zip_col):
            self.__setattr__('temp_zip_field', 'cleaned_zip_field')
            self.convert_field_to_str(self.zip_col)
            self.frame[self.temp_zip_field] = self.frame[self.zip_col].apply(
                self._zip_cleaner)
        else:
            print('Zipcodes will not be cleaned...')
        return self

    def clean_cities(self):
        if self.verify_col(self.city_col):
            self.__setattr__('temp_city_field', 'cleaned_city_field')
            self.convert_field_to_str(self.city_col)
            self.frame[self.temp_city_field] = self.frame[self.city_col].apply(
                self._city_cleaner)
        else:
            print('Cities will not be cleaned...')
        return self

    def clean_states(self):
        # todo could use fuzzy matching here to find and correct misspelled states (if using full state names)
        pass

    def geocode(self, geo_report=False):
        """
        Geocode the cleaned addresses if they exist. Geos will be added inplace to frame in new column.

        If cleaned address fields do not exist then use original.
        """
        # check if frame has cleaned field attrs
        has_temp_attrs = [hasattr(self, 'temp_add_field'),
                          hasattr(self, 'temp_city_field')]
        # if yes use them, otherwise use originals
        if all(has_temp_attrs):
            add_field, city_field = self.temp_add_field, self.temp_city_field
        else:
            add_field, city_field = self.add_col, self.city_col

        # temp geo field dict
        tgf = {'temp_ac': 'temp_add_city',
               'ac_geo': 'add_city_geo', 'a_geo': 'add_geo'}
        # 1: create add-city field and lookup
        self.frame[tgf['temp_ac']] = self.frame[add_field] + \
            ', ' + self.frame[city_field]

        # start timer for geocoder
        geocoding_start = time()
        self.frame[tgf['ac_geo']] = self.frame[tgf['temp_ac']].apply(
            self.__class__.nom.geocode)
        # 2: lookup with just add
        self.frame[tgf['a_geo']] = self.frame[add_field].apply(
            self.__class__.nom.geocode)
        # stop timer for geocoder
        geocoding_stop = time()
        print(
            f'Geocoded dataset in {(geocoding_stop - geocoding_start):.2f}s.')
        # 3: combine geo fields
        self.__setattr__('geo_field', 'geo')
        self.frame[self.geo_field] = np.where(self.frame[tgf['ac_geo']].isna(
        ), self.frame[tgf['a_geo']], self.frame[tgf['ac_geo']])
        # 4: drop temp columns
        self.frame.drop(columns=tgf.values(), inplace=True)

        # 5: filter states out
        if self.state_filter:
            # where state is in state filter -> replace result with 0
            if isinstance(self.state_filter, list):
                filter_str = '|'.join(self.state_filter).upper()
                self.frame.loc[~self.frame[self.state_col].str.contains(
                    filter_str, regex=True, case=False), self.geo_field] = 0

            elif isinstance(self.state_filter, str):
                self.frame.loc[~self.frame[self.state_col].str.contains(
                    self.state_filter.upper(), regex=True, case=False), self.geo_field] = 0

        # 6: create lat/lon fields and extract
        self.frame[['lat', 'lon']] = 0
        self.frame.reset_index(drop=True, inplace=True)
        # 7: create report if true
        for i, _ in self.frame.iterrows():
            try:
                self.frame.loc[i, 'lat'], self.frame.loc[i,
                                                         'lon'] = self.frame[self.geo_field].array[i][1][0], self.frame[self.geo_field].array[i][1][1]
            except:
                self.frame.loc[i, 'lat'], self.frame.loc[i, 'lon'] = None, None
        if geo_report:
            self._create_geo_report()
        return self

    def clean_and_geocode(self, geo_report=False):
        # clean streets, cities, zips THEN geocode
        self.clean_streets().clean_cities().clean_zips().geocode()

        if geo_report:
            self._create_geo_report()

    def _create_geo_report(self):
        # wip
        num_adds = len(self.frame)
        num_no_geo = self.frame.lat.isna().sum()
        num_geos = num_adds - num_no_geo
        num_adds_filtered_by_state = self.frame.loc[self.frame[self.geo_field] == 0].shape[0]
        # adds_within_state_filter = 0
        print(f"""
            Total Addresses: {num_adds}
            State Filtered Addresses: {num_adds_filtered_by_state}
            Geo Results: {num_geos}
            Geo Result %: {(num_geos / num_adds) * 100:.2f}%
            Geo Results w/ State Filter Correction: {(num_geos / (num_adds - num_adds_filtered_by_state)) * 100:.2f}%

            """)

    @classmethod
    def test_geocoder_url(cls, url, scheme):
        try:
            Nominatim(domain=url, scheme=scheme).geocode('')
            return True
        except GeocoderUnavailable:
            print('Geocoder is not available. Please verify cls.NOM_URL')
            return False

    @classmethod
    def set_geocoder_url(cls, url, scheme='http'):
        """
        Set url of Nominatim server.
        Parameters
        ----------
        url : str
            Should be of the form XXX.XX.X.X:<PORT>
        scheme : str, default 'http'
            Scheme of url.
        """
        if cls.test_geocoder_url(url=url, scheme=scheme):
            cls.nom = Nominatim(domain=url, scheme=scheme)
            # log
            print(f'Geocoder api updated to {cls.nom.api}')
        else:
            raise requests.exceptions.ConnectionError

    def convert_field_to_str(self, column: str):
        self.frame[column] = self.frame[column].astype(str)

    def _shorten_streets(self, street: str, subs=None) -> str:
        """
        Given string of street information, remove specific information e.g suite, apt, unit.
        Also remove extra information at the end of the string.
        Params:
            street: str
                Street in the form of a typical address line 1
            subs: list of tuples | lists, default None
                List used for pattern and replacement pairings. e.g. [(pat_1, rep_1), (pat_2, rep_2)]
        """
        # if subs not provided then use default
        if subs is None:
            subs = [(r'[\s]?(suite|plaza|unit|floor).*', ''),
                    (r'\Wapt.*', ''),
                    (r'^one(?=\s)', '1'),
                    (r'(?<=\W(ln|rd|dr|pl)).*', ''),
                    (r'(?<=\Wave).*', ''),
                    (r'(?<=\Wblvd).*', '')]

        # confirm type(subs) is list. if not then return original street.
        if not isinstance(subs, list):
            return street
        # iterate over subs and replace patterns with replacements
        for tup in subs:
            try:
                street = re.sub(tup[0], tup[1], street, flags=re.I)
            except IndexError:
                print(
                    'Param subs must be list of tuples or lists. e.g. [(pat_1, rep_1), (pat_2, rep_2)]')
        return street

    def _zip_cleaner(self, zipcode: str):
        """
        Converts from 9 digit zipcode to 5 digit
        """
        if not isinstance(zipcode, str):
            zipcode = str(zipcode)
        if re.search(r'[a-zA-Z]', zipcode):
            return 0
        return re.sub(r'\-[\d]*$', '', zipcode)

    def _city_cleaner(self, city, city_abrvs=None):
        """Converts common abbreviations in city names to full words.
        Parameters
        ----------
        city : str
        city_abrvs : dict, default None
            Dictionary containing abrv:value pairs

        Returns
        -------
        str
            Returns cleaned string of city
        """
        if city_abrvs is None:
            city_abrvs = {
                r'^[E][\.\s]': 'EAST ',
                r'^[N][\.\s]': 'NORTH ',
                r'^[W][\.\s]': 'WEST ',
                r'^[S][\.\s]': 'SOUTH ',
                r'(?<!\w)ST[\.\s]': 'SAINT ',
                r'(?<!\w)STE[\.\s]': 'SAINTE '
            }
        if not isinstance(city_abrvs, dict):
            return 'abbreviation dict should be dictionary containing abrv:value pairs'

        city = city.upper()
        for abrv, full in city_abrvs.items():
            city = re.sub(abrv, full, city)
        # replace common punctuation
        city = city.replace('  ', ' ').replace("'", ' ').replace('.', '')
        return city

    def _street_cleaner(self, street, street_abrvs=None):
        """Converts common abbreviations in street names to full words.
        Parameters
        ----------
        street : str
        street_abrvs : dict, default None
            Dictionary containing abrv:value pairs

        Returns
        -------
        str
            Returns cleaned string of street
        """
        if street_abrvs is None:
            street_abrvs = {
                r'^[E][\.\s]': 'EAST ',
                r'^[N][\.\s]': 'NORTH ',
                r'^[W][\.\s]': 'WEST ',
                r'^[S][\.\s]': 'SOUTH ',
                r'hwy': 'HIGHWAY',

            }
        if not isinstance(street_abrvs, dict):
            print(street_abrvs, street)
            return 'abbreviation_dict should be dictionary containing abrv:value pairs'
        if isinstance(street, str):
            street = street.upper()
            for abrv, full in street_abrvs.items():
                street = re.sub(abrv, full, street, flags=re.I)
            # some of the replaces below are probably redundant from shorten_street function
            punc = [r'\.', r'\,', '  ', "'"]
            street = re.sub('|'.join(punc), '', street, flags=re.I)
            return street
