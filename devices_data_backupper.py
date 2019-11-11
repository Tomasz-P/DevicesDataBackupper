"""
Moduł umożliwiający backup danych konfiguracyjnych ze wskazanych urządzeń do plików.
Wersja 1.2
Autor: Tomasz Piętka
"""

import configparser, paramiko, logging, re
from pathlib import Path
from datetime import datetime


# KLASY
class DeviceDataBackupper(object):
    """Klasa do obsługi zrzucania danych konfiguracyjnych z urządzeń."""

    def __init__(self, config_filename):
        """Konstruktor klasy do obsługi zrzucania danych konfiguracyjnych z urządzeń."""
        self.CONFIG_FILENAME = config_filename
        self.__DETAIL_CMD_REGEX = re.compile(r'^(.*\w)(\s*<)(.*\w)(\s*;)(\s*)(\d*)(>)(.*$)')
        self.__DEVICES_SECTION = 'devices'
        self.__GENERAL_PARAMETERS = 'general_parameters'
        self.__bkpfiles_directory = 'bkpfiles_directory'
        self.__device_ipaddress = 'device_ip'
        self.__device_port = 'port'
        self.__device_username = 'user_name'
        self.__device_password = 'password'
        self.__device_timeout = 12

    def backup_devices_data(self):
        """Zbackupowanie danych z urządzeń do plików i zapis na dysku we wskazanym katalogu."""
        devices_to_cmdsets_dict = self.get_devices_to_cmdsets_dict(self.CONFIG_FILENAME)
        devices_list = self.get_devices_list_from_dict(devices_to_cmdsets_dict)
        commandsets_list = self.get_commandsets_list_from_dict(devices_to_cmdsets_dict)
        commandsets_dict = self.get_command_sets(self.CONFIG_FILENAME, commandsets_list)
        for device_name in devices_list:
            self.get_data_from_device_to_files(device_name, commandsets_dict[devices_to_cmdsets_dict[device_name]])

    def get_devices_to_cmdsets_dict(self, config_filename):
        """Pobranie zestawu urządzeń z pliku konfiguracyjnego i utworzenie słownika z wpisami
        nazwa_urządzenia:zestaw_dla_urządzenia.
        """
        devices = {}
        config = configparser.ConfigParser()
        config.read(config_filename)
        command_sets = config.options(self.__DEVICES_SECTION)
        for command_set in command_sets:
            dev_names = config[self.__DEVICES_SECTION][command_set].split('\n')[1:]
            for dev_name in dev_names:
                devices[dev_name] = command_set
        logging.info(f'Dictionary created - devices to command sets: {devices}')
        return devices

    def get_devices_list_from_dict(self, dict):
        """Wyodrębnienie listy urządzeń ze słownika."""
        devices_list = []
        for key in dict.keys():
            devices_list.append(key)
        logging.info(f'Devices list created: {devices_list}')
        return devices_list

    def get_commandsets_list_from_dict(self, dict):
        """Wyodrębnienie listy zestawów komend ze słownika."""
        commandsets_list = []
        for key in dict.keys():
            if dict[key] not in commandsets_list:
                commandsets_list.append(dict[key])
        logging.info(f'Command sets list created: {commandsets_list}')
        return commandsets_list

    def get_device_parameters(self, config_filename, device_name):
        """Pobranie parametrów dla danego urządzenia z pliku konfiguracyjnego i przekształcenie do formy słownika."""
        device_parameters = {}
        config = configparser.ConfigParser()
        config.read(config_filename)
        for parameter in config.options(device_name):
            device_parameters[parameter] = config[device_name][parameter]
        logging.info(f'Parameters for device: {device_name} downloaded: {device_parameters}')
        return device_parameters

    def get_command_sets(self, config_filename, commandsets_list):
        """Wyodrębnienie z pliku konfiguracyjnego zestawu komend z podziałem na urządzenia oraz pliki."""
        commandsets_dict = {}
        files_dict = {}
        config = configparser.ConfigParser()
        config.read(config_filename)
        for commandset in commandsets_list:
            for seperate_filename in config.options(commandset):
                commands_list = config[commandset][seperate_filename].split('\n')[1:]
                files_dict[seperate_filename] = commands_list
            commandsets_dict[commandset] = files_dict
            files_dict = {}
        logging.info(f'Command sets dictionary created: {commandsets_dict}')
        return commandsets_dict

    def get_data_from_device_to_files(self, device, device_command_set):
        """Pobranie danych z urządzenia do zbackup-owania."""
        try:
            print(f'Pobieranie danych dla urządzenia {device}...')
            devconnection = paramiko.SSHClient()
            devconnection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            device_parameters = self.get_device_parameters(self.CONFIG_FILENAME, device)
            devconnection.connect(hostname=device_parameters[self.__device_ipaddress], port=device_parameters[self.__device_port],
                                  username=device_parameters[self.__device_username],
                                  password=device_parameters[self.__device_password], timeout=self.__device_timeout)
            logging.info(f'Connection to device {device} established on {device_parameters[self.__device_ipaddress]}:{device_parameters[self.__device_port]}')
            for filename_suffix in device_command_set.keys():
                simple_commands, detail_commands = self.segregate_commands(device_command_set, filename_suffix)
                backup_filename = self.create_filename(device, filename_suffix)
                file_stamp = self.create_filestamp(device)
                self.write_data_to_file(file_stamp, backup_filename)
                logging.debug(f'File stamp: {file_stamp} written to backup file: {backup_filename}')
                if simple_commands:
                    for simple_command in simple_commands:
                        command_header = self.create_command_header(simple_command)
                        self.write_data_to_file(command_header, backup_filename)
                        logging.debug(f'File command header: {command_header} written to backup file: {backup_filename}')
                        stdin, stdout, stderr = devconnection.exec_command(simple_command)
                        logging.debug(f'Data for command: {simple_command} downloaded from device: {device}')
                        device_textdata = self.convert_listdata_to_textdata(stdout.readlines())
                        self.write_data_to_file(device_textdata, backup_filename)
                    logging.info(f'Data for simple commands {simple_commands} written to file: {backup_filename}')
                if detail_commands:
                    for detail_command in detail_commands:
                        matched_detail_cmd = re.search(self.__DETAIL_CMD_REGEX, detail_command)
                        main_cmd = matched_detail_cmd.group(1)
                        listing_cmd = matched_detail_cmd.group(3)
                        main_cmd_args_column_id = matched_detail_cmd.group(6)
                        logging.debug(f'Detail command transformed -> main_command: {main_cmd} ; listing_command: '
                                      f'{listing_cmd} ; variables column id: {main_cmd_args_column_id}')
                        stdin, stdout, stderr = devconnection.exec_command(listing_cmd)
                        logging.debug(f'Data for command: {listing_cmd} downloaded from device: {device}')
                        listing_command_data = stdout.readlines()[1:]
                        main_cmd_args = [position.split()[int(main_cmd_args_column_id) - 1] for position in listing_command_data]
                        logging.debug(f'Variables extracted from column id {main_cmd_args_column_id} : {main_cmd_args}')
                        for main_cmd_arg in main_cmd_args:
                            command_with_arg = main_cmd + ' ' + main_cmd_arg
                            command_header = self.create_command_header(command_with_arg)
                            self.write_data_to_file(command_header, backup_filename)
                            logging.debug(
                                f'File command header: {command_header} written to backup file: {backup_filename}')
                            stdin, stdout, stderr = devconnection.exec_command(command_with_arg)
                            logging.debug(f'Data for command: {command_with_arg} downloaded from device: {device}')
                            device_textdata = self.convert_listdata_to_textdata(stdout.readlines())
                            self.write_data_to_file(device_textdata, backup_filename)
                    logging.info(f'Data for detail commands {detail_commands} written to file: {backup_filename}')
            devconnection.close()
            logging.info(f'Connection to device: {device} closed')
        except paramiko.BadHostKeyException as bhke:
            logging.error(f'Connection error occurred for device: {device}. Server’s host key could not be verified', exc_info=True)
            print(f'\nWYSTĄPIŁ BŁĄD W TRAKCIE POŁĄCZENIA Z URZĄDZENIEM {device}!!!'
                  f'Nie można zweryfikować klucza hosta.\n', bhke)
            print('Sprawdź log programu, aby poznać szczegóły.')
        except paramiko.AuthenticationException as ae:
            logging.error(f'Connection error occurred for device: {device}. Authentication failed', exc_info=True)
            print(f'\nWYSTĄPIŁ BŁĄD W TRAKCIE POŁĄCZENIA Z URZĄDZENIEM {device}!!!'
                  f'Autentykacja zakończona niepowodzeniem.\n', ae)
            print('Sprawdź log programu, aby poznać szczegóły.')
        except paramiko.SSHException as sshe:
            logging.error(f'Connection error occurred for device: {device}. Connecting or establishing an SSH session failed', exc_info=True)
            print(f'\nWYSTĄPIŁ BŁĄD W TRAKCIE POŁĄCZENIA Z URZĄDZENIEM {device}!!!'
                  f'Próba połączenia lub ustanawiania sesji SSH zakończona niepowowdzeniem.\n', sshe)
            print('Sprawdź log programu, aby poznać szczegóły.')
        except:
            logging.error(f'Connection error occurred for device: {device}', exc_info=True)
            print(f'\nWYSTĄPIŁ BŁĄD W TRAKCIE POŁĄCZENIA Z URZĄDZENIEM {device}!!!')
            print('Sprawdź log programu, aby poznać szczegóły.')

    def segregate_commands(self, device_command_set, filename_suffix):
        """Segragacja komend - zostają podzielone na dwie grupy: komendy proste
        oraz komendy złożone, które potrzebują argumentu. Argument pobierany jest
        z komendy prostej
        """
        simple_cmds = [cmd for cmd in device_command_set[filename_suffix]
                       if not re.search(self.__DETAIL_CMD_REGEX, cmd)]
        detail_cmds = [cmd for cmd in device_command_set[filename_suffix]
                       if re.search(self.__DETAIL_CMD_REGEX, cmd)]
        return simple_cmds, detail_cmds

    def convert_listdata_to_textdata(self, listdata):
        """Przekształcenie danych pobranych z urządzenia w formacie listy na dane w postaci tekstu - linia po linii."""
        textdata = ''
        for position in listdata:
            textdata += position
        logging.debug(f'Listdata has been converted to textdata')
        return textdata

    def get_backup_dirpath(self, config_filename):
        """Pobranie ścieżki do katalogu przeznaczonego na pliki z backup-ami z pliku konfiguracyjnego."""
        config = configparser.ConfigParser()
        config.read(config_filename)
        backup_dirpath = config[self.__GENERAL_PARAMETERS][self.__bkpfiles_directory]
        logging.debug(f'Backup directory path created: {backup_dirpath}')
        return backup_dirpath

    def create_filename(self, device_name, suffix):
        """Utworzenie nazwy pliku backup-owego dla danych pobranych z urządzenia na podstawie nazwy urządzenia (device_name) oraz przyrostka (suffix) nadawanego
        na podstawie pliku konfiguracyjnego - nazwa opcji w sekcji stanowiącej zbiór komend dla danej grupy urządzeń."""
        filename = device_name + '_' + suffix + '.txt'
        logging.debug(f'Backup filename created: {filename}')
        return filename

    def write_data_to_file(self, data, filename):
        """Zapis danych do pliku."""
        config = configparser.ConfigParser()
        config.read(self.CONFIG_FILENAME)
        filepath = Path(self.get_backup_dirpath(self.CONFIG_FILENAME)) / filename
        with open(filepath, mode='a') as bkpfile:
            bkpfile.write(data)
        logging.debug(f'Data written to filepath: {filepath}')
        return 0

    def get_current_date(self):
        '''Pobiera aktualną datę i godzinę oraz zwraca w czytelnej postaci.'''
        current_date = datetime.now()
        formatted_current_date = current_date.strftime('%d-%m-%Y %H:%M:%S')
        logging.debug(f'Formatted current date created as {formatted_current_date}')
        return formatted_current_date

    def create_filestamp(self, device_name):
        """Utworzenie odcisku dla pliku."""
        time_signature = self.get_current_date()
        filestamp = 10*'*' + ' FILESTAMP ' + 10*'*' + '\nDevice Name: ' + device_name + '\nCreated: ' + time_signature + '\n' + 31*'*' + '\n'
        logging.debug('Filestamp created')
        return filestamp

    def create_command_header(self, command):
        """Utworzenie nagłówka w pliku backup-owym dla danych wynikowych wykonania wskazanej komendy."""
        command_header = '\n\n' + 40*'=' + ' ' + command + ' ' + 40*'=' + '\n\n'
        logging.debug(f'Command header for command: {command} created')
        return command_header