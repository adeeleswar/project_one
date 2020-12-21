```text
SPDX-License-Identifier: Apache-2.0
Copyright (c) 2020 Intel Corporation
```

# EIS Applications with OpenNESS
The purpose of this source code is to deploy EIS applications on OpenNESS platform.

Edge Insights Software (EIS) is the framework for enabling smart manufacturing with visual and point defect inspections.

More details about EIS:  
[https://www.intel.com/content/www/us/en/internet-of-things/industrial-iot/edge-insights-industrial.html](https://www.intel.com/content/www/us/en/internet-of-things/industrial-iot/edge-insights-industrial.html)

Currently, `eis-experience-kit` supports EIS in version 2.3.1

- [Pre-requisites](#pre-requisites)
- [Installation Process](#installation-process)
    - [Getting The Sources](#getting-the-sources)
    - [Build Stage](#build-stage)
    - [Deploy Stage](#deploy-stage)
    - [Cleanup](#cleanup)
- [Configuration](#configuration)
    - [Getting Sources Settings](#getting-sources-settings)
    - [Build Settings](#build-settings)
    - [Deploy Settings](#deploy-settings)
    - [Inventory](#inventory)
    - [Playbook Main File](#playbook-main-file)
    - [EIS Demo Setting](#eis-demo-setting)
        - [RTSP Stream Setting](#rtsp-stream-setting)
    - [View Visualizer Setting](#view-visualizer-setting)
- [Installation](#installation)
- [Web Visualizer Display](#web-visualizer-display)
- [Removal](#removal)
- [References](#references)


## Pre-requisites
EIS applications require Network Edge OpenNESS platform to be deployed and working.

## Installation Process
The major part of this repository is Ansible scripts set. They are used for EIS application build and deployment. Most of the roles are split into two stages - build and deploy. The first part is performed on the same host as Ansible scripts and the second one is run on OpenNESS Master Node.

User can manage which components will be executed during the deployment.

### Getting The Sources
`eis-experience-kit` supports two ways of getting EIS sources. User can choose between cloning the repository from Git and use release package.

To use the release package, user should get it manually and the path to it should be passed in `host_vars/localhost.yml` file in field `release_package_path`. The package will be extracted and source code will be used in the same way as repository.

The release package can be downloaded here: [https://software.intel.com/content/www/us/en/develop/topics/iot/edge-solutions/industrial-recipes.html](https://software.intel.com/content/www/us/en/develop/topics/iot/edge-solutions/industrial-recipes.html)

### Build Stage
Overview on `eis-experience-kit` architecture:

![eis-experience-kit architecture](docs/images/eis_deployment_diagram.png)

All the `build` tasks are perfomed on `localhost`. It is the same machine that Ansible Playbook is run on. These tasks contain installation of all required prerequisites for building the applications images and all steps related to building docker images. All images, after successful build, are tagged and pushed to the Docker Registry that is a part of OpenNESS platform. They will be used by Kubernetes later, in `deploy` stage. 

### Deploy Stage
`Deploy` tasks are executed on OpenNESS Master Node. These tasks include ETCD certificates and ZMQ keys generation process and adding apps configs to ETCD. All these things are done just before the particular application has been deployed. For the deployment `kubectl` command and Kubernetes manifest files have been used. 

### Cleanup
All the roles in Ansible Playbook have clean up scripts that can be run to reverse the build and deploy tasks. It should be used only for debug purposes. It is not guarantee that clean up scripts will remove everything that has been added by build & deployment stages. In the most cases it is enough for running the deployment of particular application or the whole EIS again. `cleanup_eis_pcb_demo.sh` is a shell scripts that is running a sequence of cleaning tasks that should cover all the `deploy_eis_pcb_demo.sh` changes on the setup.

## Configuration
User can configure the installation of EIS by modifying the files that contain variables used widely in Ansible Playbook. All the variables that can be adjusted by the user are placed in `host_vars` directory.

### Getting Sources Settings
`eis-experience-kit` supports two ways of getting sources. It can be done by cloning the repository using git or use pre-downloaded release package. The first one can be chosen by setting `eis_source` to `gitclone`. User needs to be authorized to clone the repo from Gitlab and may be asked for credentials (or ssh key needs to be added to the Gitlab account). The second one requires `eis_source` to be set to `release` and `release_package_path` to be set to the release package path. Then package will be automatically extracted and used by Ansible scripts. These settings are available in `host_vars/localhost.yml`.

### Build Settings
`localhost.yml` file contains all the settings specific for build process that is performed on localhost. User can set proxy settings and how the EIS sources will be handled.

### Deploy Settings
The second one is regarding the `deploy` process. All the settings are in `openness_controller.yml` file. It is for the action that will occur on OpenNESS Master Node. It contains mostly the values for certificates generation process and paths for Kubernetes deployment related files.

### Inventory
User needs to set the OpenNESS Master Node IP address. It can be done in `inventory.ini` file.

### Playbook Main File
The main file for playbook is `eis_pcb_demo.yml`. User can define here which roles should be run during the build & deployment. They can be switch by using comments for unnecessary roles.

### EIS Demo Setting
eis-experience-kit currently  we can configure for  Demo type as 

- PCB Demo
- Safety Demo

Following flags controll for configuring demo type on `group_vars/all.yml
```sh
demo_type: "safety"  -> for Safety Demo
demo_type: "pcb"     -> for PCB Demo
```
#### RTSP Stream Setting
Currently RTSP camera steam data can be received follwing source  
   - rtsp stream from  camera-stream pod
   - rtsp stream from Linux host
   - rtsp stream from Window host

on eis-experience-kit  demo  default rtsp strem  will recive from camera-stream pod.
Follwing flags are contrl for receving receiving rtsp strem on `group_vars/all.yml`

#### Enable rtsp stream from  camera-stream pod(Default)
```sh
    camera_stream_pod: true  
    rtsp_camera_stream_ip: "ia-camera-stream-service" 
    rtsp_camera_stream_port: 8554               
```
#### Enable rtsp stream from  extrnal Linux/Window host
 ```sh
    camera_stream_pod: false  
    rtsp_camera_stream_ip: "192.169.1.1"   < update Linux/window external rtsp server IP>
    rtsp_camera_stream_port: 8554               
```

####  Send rtsp stream from external Linux (CentOS)
```sh
yum install -y epel-release  https://download1.rpmfusion.org/free/el/rpmfusion-free-release-7.noarch.rpm
yum install -y vlc
sed -i 's/geteuid/getppid/' /usr/bin/vlc
./send_rtsp_stream_linux.sh <file_name> <port_name>
```
####  Send rtsp stream from external Linux (ubuntu)

```sh
apt-get install vlc
sed -i 's/geteuid/getppid/' /usr/bin/vlc
./send_rtsp_stream_linux.sh <file_name> <port_name>
```
####  Send rtsp stream from external Windows Host

```sh
#install  vlc player <https://www.videolan.org/vlc/download-windows.html>
#update follwing varaible on  send_rtsp_stream_linux.sh
set vlc_path="c:\Program Files (x86)\VideoLAN\VLC"
set file_name="c:\Data\Safety_Full_Hat_and_Vest.avi"  < update Demo file name>
set port="8554"
#next run   send_rtsp_stream_win.bat file 
```

**Note**: Following script and demo video file should copied from ansible host machine

    `/eis-experience-kit/scripts/send_rtsp_stream_linux.sh`
    `/eis-experience-kit/scripts/send_rtsp_stream_win.bat`
    `/opt/eis_repo/IEdgeInsights/VideoIngestion/test_videos/pcb_d2000.avi`
    `/opt/eis_repo/IEdgeInsights/VideoIngestion/test_videos/Safety_Full_Hat_and_Vest.avi`


### View Visualizer HOST Server
Currently default setting is enabled for **web_visualizer**.
This setting is `optional` only if we want to view visualizer on any HOST server, Update IP Adddress of host server where we want to see the GUI output, Visualizer container will expose the GUI output on display host.
```sh 
display_visualizer_host: true
display_host_ip: "192.168.0.1"     < Update Display Host IP>
display_no: "1"                    <Update Display no>
```

**Note**: 
- Display host shoud have GUI/VNC access and check the Display by echo $DISPLAY 
update the display on above `display_no`.
- configure `xhost +` on Display host for receiving  video GUI  

## Installation
After all the configuration is done, script `deploy_eis.sh` needs to be executed to start the deployment process. No more actions are required, all the installation steps are fully automated. 

## Web Visualizer display

After EIS deployed successfully output can be viewed using

`https://<controller_IP>:5050`

username:`admin`

password:`admin@123`

**Note**:
Open Web Visualizer on google chrome browser, if Your connection is not private show, select Advanced option and proceed to.


## Removal
To clean up the platform from EIS applications `cleanup_eis_deployment.sh` script can be used. It runs Ansible playbook `eis_cleanup.yml` and processes all the roles defined there. Inventory file is used for getting Controller Node IP.

## References
- [Industrial Edge Insights Application on OpenNESS - Solution Overview](https://github.com/open-ness/specs/blob/master/doc/applications/openness_eis.md)
- [Intel’s Edge Insights for Industrial](https://www.intel.com/content/www/us/en/internet-of-things/industrial-iot/edge-insights-industrial.html)
