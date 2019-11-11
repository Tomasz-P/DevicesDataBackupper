#! python3
"""
Pobieranie danych na temat konfiguracji z urządzeń, umieszczanie ich w plikach we wskazanym katalogu.
Dane dotyczące urządzeń, ich adresacji, danych dostępowych, komend do wydania pobierane są z pliku konfiguracyjnego "config_file.ini"
z wykorzystaniem modułu "configparser"-a.
"""

from devices_data_backupper import DeviceDataBackupper
from pathlib import Path
from os import path, scandir, rename
import configparser
import logging
import re


# FUNKCJE
def add_numbersuffix_to_filename(full_filename):
    """Dodanie suffix-u do nazwy pliku logów, gdy jego rozmiar przekroczy wartość logfile_size podaną w bajtach.
    Zapis kolejnych logów odbywa się do kolejnego pliku bez suffix-u, nowo utworzonego.
    """
    filename = Path(full_filename).stem
    filename_extension = Path(full_filename).suffix[1:]
    numbers = []
    fileRegex = re.compile('(^' + filename + '_)(\d{4})\.(' + filename_extension + '$)')
    with scandir('.') as entries:
        for entry in entries:
            matched_fullfilename = re.search(fileRegex, entry.name)
            if matched_fullfilename:
                numbers.append(int(matched_fullfilename.group(2)))
    numbers.sort()
    next_number = (numbers[-1] + 1)
    numbered_fullfilename = filename + (4 - len(str(next_number))) * '0' + str(next_number) + '.'\
                            + filename_extension
    rename(full_filename, numbered_fullfilename)
    return 0

def set_logging(logfilename, logging_level, logfile_maxsize):
    '''Ustawienie poziomu logowania zdarzeń w trakcie wykonywania programu.'''
    if Path(logfilename).exists() and path.getsize(logfilename) >= int(logfile_maxsize):
        add_numbersuffix_to_filename(logfilename)
    if logging_level == 'CRITICAL':
        logging.basicConfig(filename=logfilename, filemode='a', level=logging.CRITICAL,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    elif logging_level == 'ERROR':
        logging.basicConfig(filename=logfilename, filemode='a', level=logging.ERROR,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    elif logging_level == 'WARNING':
        logging.basicConfig(filename=logfilename, filemode='a', level=logging.WARNING,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    elif logging_level == 'INFO':
        logging.basicConfig(filename=logfilename, filemode='a', level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    else:
        logging.basicConfig(filename=logfilename, filemode='a', level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f'Logging level set to {logging_level} for file {logfilename}.')
    return 0

def main():
    """Funkcja główna."""
    try:
        print('Uruchomiono program.')
        CONFIG_FILENAME = 'config_file_home1.ini'
        CFG_GENERAL_PARAMETERS = 'general_parameters'
        CFG_LOGFILENAME = 'logfilename'
        CFG_LOG_LEVEL = 'log_level'
        CFG_LOGFILE_MAXSIZE = 'logfile_maxsize'

        config = configparser.ConfigParser()
        config.read(CONFIG_FILENAME)
        set_logging(config[CFG_GENERAL_PARAMETERS][CFG_LOGFILENAME], config[CFG_GENERAL_PARAMETERS][CFG_LOG_LEVEL],
                    config[CFG_GENERAL_PARAMETERS][CFG_LOGFILE_MAXSIZE])
        backupper = DeviceDataBackupper(CONFIG_FILENAME)
        backupper.backup_devices_data()
        logging.info('The program has been completed')
        print('Program zakończył działanie.')
    except:
        print('\nWYSTĄPIŁ BŁĄD W TRAKCIE WYKONYWANIA PROGRAMU!!!\nWięcej informacji w pliku logów.\n')
        logging.error('An error has occurred! The program ended with an exception: ', exc_info=True)

# PROGRAM GŁÓWNY
if __name__ == "__main__":
    main()