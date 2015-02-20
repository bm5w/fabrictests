# fabrictests
When uploading projects with fab
place files to be uploaded in /upload directory
upload directory must contain supervisord.conf
    this file must be edited with proper .py name
simple_nginx_config_template must also be present
    fabric will modify this template using RE to find 'xxxx'
    and replace with the correct server link.