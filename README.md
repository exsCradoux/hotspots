# fragment_hotspot_maps

## Installation instructions for fragment-hotspot-maps 0.1 
---------------------------------------------------------

### 1. Clone github repository _(currently only available to collaborators)_
1.1 Make installation directory

`mkdir <repo_dir>`

1.2 Clone repository

`git clone git@github.com:prcurran/fragment_hotspot_maps.git`

1.3 Create fragment-hotspot-maps zip

`cd <repo_dir>/fragment_hotspot_maps`

`python create_hotspot_zip.py`

***
### Install CSDS 2018

2.1 Available from [CCDC downloads page](https://www.ccdc.cam.ac.uk/support-and-resources/csdsdownloads/) _(site number and confirmation code **required**_)

### 3. Create Python environment

3.1 Activate CSDS miniconda environment

`<CSDS location>\Python_API_2018\miniconda\Scripts\activate.bat`

3.2 Make an exact copy of the CSDS Python environment

`conda create -n <env_name> python`

3.3 Activate environment

`activate <env_name>`

### 4. Install fragment-hotspot-maps 0.1

4.1 Navigate to cloned github repository

`cd <repo_dir>`

4.2 Install fragment-hotspot-maps 0.1 using pip

`pip install fragment_hotspot_maps.zip`
***

### 5. Linux users only

5.1 Set CSD environment variables in bash

`vi bash`

add the following lines:

    export CSDHOME=/<user_path>/CCDC/CSD_2018
    export SUPERSTAR_ROOT=/<user_path>/CCDC/GoldSuite_2018/SuperStar/
    export SUPERSTAR_ISODIR=/<user_path>/CCDC/CSD_2018/isostar_files/istr/

***
## FAQs


 