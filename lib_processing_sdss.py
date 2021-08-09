import os
import glob
import time
import urllib
import sys

import astropy.io.fits as pyfits
from functools import partial
import matplotlib
import matplotlib.pyplot as plt
import multiprocessing as mp
import numpy as np
import pandas as pd
from sklearn import preprocessing

from constants_sdss import number_waves, wave_master
#from constants_sdss import working_dir, science_arxive_server_path
#from constants_sdss import processed_spectra_path, spectra_path
################################################################################
# helper_function

################################################################################
class FitsPath:
    ############################################################################
    def __init__(self, galaxies_df, n_processes):

        self.galaxies_df = galaxies_df
        self.n_processes = n_processes
    ############################################################################
    def decode_base36(self, sub_class:'str'):

        if ' ' in sub_class:
            sub_class = sub_class.replace(' ', '')

        elif sub_class == '':
            sub_class = 'EC'

        return int(sub_class, 36)
    ############################################################################
    def encode_base36(self, sub_class:'int'):

        alphabet, base36 = ['0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', '']

        sub_class = abs(int(sub_class))

        while sub_class:
            sub_class, i = divmod(sub_class, 36)
            base36 = alphabet[i] + base36

        return base36 or alphabet[0]
    ############################################################################
    def class_sub_class(self, fits_paths:'list'):

        with mp.Pool(processes=self.n_processes) as pool:
            res = pool.map(self._class_sub_class, fits_paths)

        return res
    ############################################################################
    def _class_sub_class(self, fits_path:'str'):

        with pyfits.open(fits_path) as hdul:
            classification = hdul[2].data['CLASS']
            sub_class = hdul[2].data['SUBCLASS']

        return sub_class #[classification, sub_class]
    ############################################################################
    def get_all_paths(self):

        params = range(len(self.galaxies_df))

        with mp.Pool(processes=self.n_processes) as pool:
            res = pool.map(self._get_path, params)

        return res
    ############################################################################
    def _get_path(self, galaxy_index:'int'):

        galaxy_fits_path, fname = self._galaxy_fits_path(galaxy_index)

        return galaxy_fits_path
    ############################################################################
    def _galaxy_fits_path(self, galaxy_index:'int'):

        galaxy = self.galaxies_df.iloc[galaxy_index]
        plate, mjd, fiberid, run2d = self._galaxy_identifiers(galaxy)

        fname = f'spec-{plate}-{mjd}-{fiberid}.fits'

        SDSSpath = f'sas/dr16/sdss/spectro/redux/{run2d}/spectra/lite/{plate}'
        retrieve_path = f'{spectra_path}/{SDSSpath}'

        return f'{retrieve_path}/{fname}', fname
    ############################################################################
    def _galaxy_identifiers(self, galaxy):

        plate = f"{galaxy['plate']:04}"
        mjd = f"{galaxy['mjd']}"
        fiberid = f"{galaxy['fiberid']:04}"
        run2d = f"{galaxy['run2d']}"

        return plate, mjd, fiberid, run2d
################################################################################
class DataProcessing:

    def __init__(self, galaxies_frame:'pd.df',number_processes:'int'):
        """
        INPUTS

        OUTPUT
        """
        self.df = galaxies_frame
        self.number_processes = number_processes
    ############################################################################
    def interpolate_spectra(self, wave_master: 'np.array',
        data_directory:'str', output_directory:'str'):
        """
        Interpolate rest frame spectra from data directory according to
        wave master  and save it to output directory

        INPUTS
            wave_master: 1 dimensional array containing the common grid
                to use with all spectra
            data_directory:
            output_directory:

        OUTPUT
        """
        print(f'Interpolate spectra...')
# use a partial from itertools for interpolate function
        galaxy_indexes = range(self.df.shape[0])

        with mp.Pool(processes=self.number_processes) as pool:
            results = pool.map(self._interpolate, galaxy_indexes)
            number_failed = sum(results)

        print(f'Spectra saved. Failed to save {number_failed}')

    def _interpolate(self, galaxy_index:'str'):
        """
        Function to interpolate single spectrum to wav master

        INPUT
            galaxy_index: index to locate given galaxy in the meta data frame

        OUTPUT
        """

        spectrum = np.load()

    def normalize_spectra(self, spectra:'np.array'):
        """"""

        # spectra[:, :] *= 1/np.median(spectra[:, :], axis=1).reshape(
        #         (spectra.shape[0], 1))

       #  return spectra
       pass

    def missing_flux_replacement(self, spectra:'array', method:'str'='median'):

        if method=='median':

            mask_replacement = ~np.isfinite(spectra)
            for idx, mask in enumerate(mask_replacement):
                spectra[idx, mask] = np.nanmedian(spectra[idx, :])

        elif method=='mean':

            mask_replacement = ~np.isfinite(spectra)
            for idx, mask in enumerate(mask_replacement):
                spectra[idx, mask] = np.nanmean(spectra[idx, :])

        return spectra

    def indefinite_values_handler(self, spectra:'np.array',
        discard_fraction:'float'=0.1):
        #global wave_master

        print(f'spectra shape before keep_spec_mask: {spectra.shape}')

        n_indef = np.count_nonzero(~np.isfinite(spectra), axis=0)
        print(f'Indefinite vals in the input array: {np.sum(n_indef)}')

        keep_flux_mask =  n_indef < spectra.shape[0]*discard_fraction

        spectra = spectra[:, keep_flux_mask]
        print(f'spectra shape after keep_spec_mask: {spectra.shape}')

        wave = wave_master[keep_flux_mask[: -8]]

        n_indef = np.count_nonzero(~np.isfinite(spectra), axis=0)
        print(f'Indefinite vals in the NEW array: {np.sum(n_indef)}')

        return spectra, wave

    def spec_to_single_array(self, fnames: 'list'):

        n_spectra = len(fnames)
        n_fluxes = np.load(fnames[0]).size

        spectra = np.empty((n_spectra, n_fluxes))

        for idx, file_path in enumerate(fnames):

            fname = file_path.split('/')[-1].split('_')[0]

            print(f"Loading {fname} to single array", end='\r')

            spectra[idx, :] = np.load(file_path)

        return spectra
################################################################################
class RawData:

    def __init__(self, galaxies_df:'pd.df',
        data_directory:'str', output_directory:'str',
        number_processes:'int'):
        """
        INPUT

        galaxies_df : data frame containing meta data from sdss spectra
        data_directory : sdss raw data's directory
        output_directory : redshift corrected spectra's and meta data directory
        number_processes : number of processes to use with mp.Pool

        OUTPUT
        RawDataProcessing object
        """

        self.df = galaxies_df
        self.number_processes = number_processes

        self.data_directory = data_directory

        if not os.path.exists(self.data_directory):
            print(f'Path: {self.data_output_directory} does not exist!')

        self.data_output_directory = output_directory
        self.rest_frame_directory = f"{output_directory}/rest_frame"

        if not os.path.exists(self.data_output_directory):
            os.makedirs(self.data_output_directory)
            os.makedirs(f"{self.rest_frame_directory}")


        self.meta_data_frame = None
    ############################################################################
    def get_raw_spectra(self):
        """
        Save data frame with all meta data

        INPUTS
            None

        OUTPUT
            None
        """

        print(f'Saving raw redshift corrected spectra and meta-data!')

        galaxy_indexes = range(self.df.shape[0])

        with mp.Pool(processes=self.number_processes) as pool:
            results = pool.map(self._get_spectra, galaxy_indexes)

        self.meta_data_frame = pd.DataFrame(
            results,
            columns=['name', 'z', 'snr', 'run2d', 'sub-class', 'class'])

    def _get_spectra(self, galaxy_index:'int'):
        """
        Gets a row of meta data

        INPUT
            galaxy_index: index of a galaxy in that galaxy that the frame
            passed to the constructor of the class

        OUTPUT
            meta data list, intended to be a row in the meta_data_frame:
                meta_data_frame: [name: galaxy name,
                z: redshift,
                snr: signal to noise ratio,
                run2d,
                sub-class: sdss classification,
                class: sdss classification]
        """

        sdss_directory, spectra_name, run2d = self._galaxy_localization(
            galaxy_index)

        [plate, mjd, fiberid] = spectra_name.split('-')[1:]

        galaxy_fits_location = f'{sdss_directory}/{spectra_name}.fits'

        if not os.path.exists(galaxy_fits_location):

            print(f'{spectra_name}.fits file not found')

            meta_data = [spectra_name, np.nan, np.nan, run2d, np.nan, np.nan]

            return meta_data

        else:

            [wave, flux, z, signal_noise_ratio,
                classification, sub_class] = self._rest_frame(galaxy_index,
                                                 galaxy_fits_location)

            np.save(f"{self.rest_frame_directory}/{spectra_name}.npy",
                np.vstack((wave, flux)))

            meta_data = [spectra_name, z, signal_noise_ratio, run2d,
                classification, sub_class]

            return meta_data

    def _rest_frame(self, galaxy_index:'int', galaxy_fits_location:'str'):
        """
        De-redshifting

        INPUT
            galaxy_index: index of the galaxy in the input data frame
                passed to the constructor
            galaxy_fits_location: directory location of the fits file

         OUTPUT
            return wave, flux, z, signal_noise_ratio, classification, sub_class
                wave: de-redshifted wave length
                flux: flux
                z: redshift
                signal_noise_ratio: signal to noise ratio
                classification: sdss pipeline classification
                sub_class: sdss subclass pipeline classification
        """

        with pyfits.open(galaxy_fits_location) as hdul:
            wave = 10. ** (hdul[1].data['loglam'])
            flux = hdul[1].data['flux']
            classification = hdul[2].data['CLASS'][0]
            sub_class = hdul[2].data['SUBCLASS'][0]


        z = self.df.iloc[galaxy_index]['z']
        z_factor = 1./(1. + z)
        wave *= z_factor

        signal_noise_ratio = self.df.iloc[galaxy_index]['snMedian']

        return wave, flux, z, signal_noise_ratio, classification, sub_class

    def _galaxy_localization(self, galaxy_index:'int'):
        """
        INPUTS
            galaxy_index: index of the galaxy in the input data frame
                passed to the constructor

        OUTPUTS
            return sdss_directory, spectra_name, run2d

                sdss_directory: directory location of the spectra fits file
                spectra_name: f'spec-{plate}-{mjd}-{fiberid}'
                run2d: PENDING
        """

        galaxy = self.df.iloc[galaxy_index]
        plate, mjd, fiberid, run2d = self.galaxy_identifiers(galaxy)

        spectra_name = f'spec-{plate}-{mjd}-{fiberid}'

        sdss_directory = (f'{self.data_directory}/sas/dr16/sdss/spectro/redux'
            f'/{run2d}/spectra/lite/{plate}')

        return sdss_directory, spectra_name, run2d
    ############################################################################
    def galaxy_identifiers(self, galaxy:'df.row'):
        """
        INPUT
            galaxy : pd.row from the galaxy data frame passed to
                the constructor of the class

        OUTPUT
            return plate, mjd, fiberid, run2d

                plate: self explanatory
                mjd: date
                fiberid: self explanatory
                run2d: PENDING

        """

        plate = f"{galaxy['plate']:04}"
        mjd = f"{galaxy['mjd']}"
        fiberid = f"{galaxy['fiberid']:04}"
        run2d = f"{galaxy['run2d']}"

        return plate, mjd, fiberid, run2d
################################################################################
class DownloadData:

    def __init__(self, files_data_frame, download_path, n_processes):
        """
        files_data_frame: Pandas DataFrame with all the imformation of the sdss
        galaxies

        download_path: (string) Path where the data will be downloaded
        """
        self.data_frame = files_data_frame
        self.download_path = download_path
        self.n_processes = n_processes

    def get_files(self):

        print(f'*** Getting {len(self.data_frame)} fits files ****')
        start_time_download = time.time()

        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

        params = range(len(self.data_frame))

        with mp.Pool(processes=self.n_processes) as pool:
            res = pool.map(self._get_file, params)
            n_failed = sum(res)

        finish_time_download = time.time()

        print(f'Done! Finished downloading .fits files...')
        print(f'Failed to download {n_failed} files' )
        print(
            f'Download took {finish_time_download-start_time_download:.2f}[s]')


    def _get_file(self, idx_data_frame):

        object = self.data_frame.iloc[idx_data_frame]
        plate, mjd, fiberid, run2d = self._file_identifier(object)

        fname = f'spec-{plate}-{mjd}-{fiberid}.fits'

        SDSSpath = f'sas/dr16/sdss/spectro/redux/{run2d}/spectra/lite/{plate}'
        folder_path = f'{self.download_path}/{SDSSpath}'

        url =\
        f'https://data.sdss.org/{SDSSpath}/{fname}'

        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        # Try & Except a failed Download

        try:
            self._retrieve_url(url, folder_path, fname)
            return 0

        except Exception as e:

            print(f'Failed : {url}')

            print(f'{e}')
            return 1

    def _retrieve_url(self, url, folder_path, fname):

        if not(os.path.isfile(f'{folder_path}/{fname}')):

            print(f'Downloading {fname}', end='\r')

            urllib.request.urlretrieve(url, f'{folder_path}/{fname}')

            file_size = os.path.getsize(f'{folder_path}/{fname}')

            j = 0

            while j < 10 and (file_size < 60000):

                os.remove(f'{folder_path}/{fname}')
                urllib.request.urlretrieve(url, f'{folder_path}/{fname}')
                j += 1
                time.sleep(1)

            file_size = os.path.getsize(f'{folder_path}/{fname}')

            if file_size < 60000:
                print(f"Size of {fname}: {file_size}... Removing file!!")
                os.remove(f'{folder_path}/{fname}')
                raise Exception("Spectra wasn't found")

        else:
            print(f'{fname} already downloaded!!', end='\r')


    def _file_identifier(self, object):

        plate = f"{object['plate']:04}"
        mjd = f"{object['mjd']}"
        fiberid = f"{object['fiberid']:04}"
        run2d = f"{object['run2d']}"

        return plate, mjd, fiberid, run2d
