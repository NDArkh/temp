import json
from time import sleep
from pathlib import Path
from datetime import datetime as dt
from selenium import webdriver
import logging
from selenium.common import exceptions as webex
from selenium.webdriver.remote import webelement as web


def get_wdriver(proxy: str = None):
    options = webdriver.ChromeOptions()

    if proxy is not None:
        options.add_argument(f'--proxy-server=http://{proxy}')
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-extensions')
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--start-maximized")
    options.add_argument("--headless")

    drive = webdriver.Chrome(options=options)
    drive.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': """
        Object.defineProperty(Navigator.prototype, 'webdriver', {
            set: undefined,
            enumerable: true,
            configurable: true,
            get: new Proxy(
                Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver').get,
                { apply: (target, thisArg, args) => {
                    // emulate getter call validation
                    Reflect.apply(target, thisArg, args);
                    return false;
                }}
            )
        });
    """})

    return drive


def get_crd_dict_node(line: web.WebElement, station_type: str):
    def _float(value):
        return round(float(value), 1)

    def _inner(value):
        return value.get_attribute('innerHTML')

    cells = list(map(_inner, line.find_elements_by_tag_name('td')))

    return {
        'N': int(cells[0]),
        'type': station_type,
        'station': str(cells[1]),
        'precipitation': int(cells[2]),
        'humidity': {
            'min_p': int(cells[3]),
            'max_p': int(cells[4]),
            'avg_p': int(cells[5])
        },
        'temperature': {
            'min_c': _float(cells[6]),
            'max_c': _float(cells[7]),
            'avg_c': _float(cells[8])
        },
        'wind_speed': _float(cells[9])
    }


def get_crd_lines(wdrive, logger: logging.Logger):
    """
    :param wdrive: initialized webdriver
    :param logger: used logger
    :return: iterable webelements
    """
    wdrive.get('https://www.ncm.ae/services/climate-reports-daily?lang=en')
    retr = 0
    while retr < 10:
        if retr > 0:  # sleep becaose of retry
            logger.warning(f'wait {retr / 2} secL don\'t see the table')
            sleep(retr / 2)

        try:  # try to get table
            return wdrive.find_element_by_css_selector(
                '#pageContainer > div > div > div.table-wrapper.bg-light.shadow-sm.p-4 > div > table')\
                .find_element_by_tag_name('tbody')\
                .find_elements_by_tag_name('tr')
        except webex.NoSuchElementException:  # table was not loaded yet
            retr += 1
        except Exception as ex:
            logger.error(f'UNKNOWN EXEPTION ({type(ex)})\nINFO:\t{repr(ex)}')


def main(_log: logging.Logger,
        is_crd: bool = False, is_aws: bool = False,
        proxy: str = None, outer_fpath: str = '.',
        fname_crd: str = 'climate_reports_daily.json'
):
    _log.info(f'started with parameters:\n\tis_crd={is_crd},\n\tis_aws={is_aws},'
              f'\n\tproxy={proxy},\n\touter_fpath={outer_fpath},\n\tfname_crd={fname_crd}')
    wdrive = get_wdriver()
    _log.info('Selenium WebDriver (Chrome) started')

    if is_crd:
        _log.info('working at https://www.ncm.ae/services/climate-reports-daily?lang=en')
        _json, current_type = list(), ''

        for line in get_crd_lines(wdrive, _log):
            if str(line.get_attribute('innerHTML')).count('td') == 2:
                current_type = line.find_element_by_tag_name('td').get_attribute('innerHTML')

            else:
                _json.append(get_crd_dict_node(line, current_type))
        _log.info(f'get {len(_json)} nodes')

        Path(outer_fpath).mkdir(exist_ok=True)
        _fpath = Path(outer_fpath, f'{dt.now().date().strftime("%Y%m%d")}_{fname_crd}')
        with open(_fpath, 'w', encoding='utf-8') as fjson:
            json.dump(_json, fjson)
            _log.info(f'saved file as {_fpath}')

        del _json, current_type

    if is_aws:
        _log.warning('https://www.ncm.ae/maps-aws-stations/dry-temperature?lang=en '
                     'parsing is not realized yet!')

    wdrive.close()


if __name__ == '__main__':

    log = logging.getLogger()
    try:
        main(log, is_crd=True)
    except webex.WebDriverException as ex:
        if 'ERR_PROXY_CONNECTION_FAILED' in str(ex):
            log.error('can\'t connect proxy!')
        else:
            log.error(f'UNKNOWN EXCEPTION {type(ex)}\n\tINFO:\t{repr(ex)}')
