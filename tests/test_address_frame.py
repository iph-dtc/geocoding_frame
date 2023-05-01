import pytest
import pandas as pd
from requests.exceptions import ConnectionError
from address_frame import AddressFrame


@pytest.fixture
def frame():
    return pd.read_csv('../data/test_adds.csv')


@pytest.fixture
def address_frame(frame):
    return AddressFrame(frame, 'address', 'city', 'state', 'zipcode',)


@pytest.fixture
def get_cleaned_streets():
    return ['5201 SOUTHWEST AVE', '2225 MACKLIND AVE', '1934 MACKLIND AVE', '5256 WILSON AVE', '5046 SHAW AVE']


@pytest.fixture
def get_cleaned_zips():
    return ['63139', '63110', '63110', '63110', '63110']


def test_set_geocoder_url(address_frame):
    adf = address_frame
    with pytest.raises(ConnectionError) as e:
        adf.set_geocoder_url('172.16.0.1:8989')
    adf.set_geocoder_url('172.18.0.1:8989')
    assert adf.nom.api == 'http://172.18.0.1:8989/search'


def test_convert_field_to_str(address_frame, column='address'):
    adf = address_frame
    adf.convert_field_to_str(column)
    assert adf.frame['address'].dtype == 'object'


def test_clean_streets(address_frame, get_cleaned_streets):
    adf = address_frame
    adf.clean_streets()
    assert adf.frame[adf.temp_add_field].to_list() == get_cleaned_streets


def test_clean_zips(address_frame, get_cleaned_zips):
    adf = address_frame
    adf.clean_zips()
    assert adf.frame[adf.temp_zip_field].to_list() == get_cleaned_zips
