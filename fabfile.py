from fabric.api import run
from fabric.api import env
import boto.ec2
import time
from fabric.api import prompt
from fabric.api import execute
from fabric.api import sudo
from fabric.contrib.files import sed
from fabric.contrib.project import upload_project
import os

env.hosts = ['localhost', ]
env.aws_region = 'us-west-2'


def host_type():
    run('uname -s')


def get_ec2_connection():
    if 'ec2' not in env:
        conn = boto.ec2.connect_to_region(env.aws_region)
        if conn is not None:
            env.ec2 = conn
            print "Connected to EC2 region %s" % env.aws_region
        else:
            msg = "Unable to connect to EC2 region %s"
            raise IOError(msg % env.aws_region)
    return env.ec2


def provision_instance(wait_for_running=False, timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    conn = get_ec2_connection()
    instance_type = 't1.micro'
    key_name = 'pk-aws'
    security_group = 'ssh-access'
    image_id = 'ami-810a2fb1'

    reservations = conn.run_instances(
        image_id,
        key_name=key_name,
        instance_type=instance_type,
        security_groups=[security_group, ]
    )
    new_instances = [i for i in reservations.instances if i.state == u'pending']
    running_instance = []
    if wait_for_running:
        waited = 0
        while new_instances and (waited < timeout_val):
            time.sleep(wait_val)
            waited += int(wait_val)
            for instance in new_instances:
                state = instance.state
                print "Instance {} is {}".format(instance.id, state)
                if state == 'running':
                    running_instance.append(
                        new_instances.pop(new_instances.index(i))
                    )
                instance.update()


def list_aws_instances(verbose=False, state='all'):
    conn = get_ec2_connection()

    reservations = conn.get_all_reservations()
    instances = []
    for res in reservations:
        for instance in res.instances:
            if state == 'all' or instance.state == state:
                instance = {
                    'id': instance.id,
                    'type': instance.instance_type,
                    'image': instance.image_id,
                    'state': instance.state,
                    'instance': instance,
                }
                instances.append(instance)
    env.instances = instances
    if verbose:
        import pprint
        pprint.pprint(env.instances)


def select_instance(state='running'):
    if env.get('active_instance', False):
        return

    list_aws_instances(state=state)

    prompt_text = "Please select from the following instances:\n"
    instance_template = " %(ct)d: %(state)s instance %(id)s\n"
    for idx, instance in enumerate(env.instances):
        ct = idx + 1
        args = {'ct': ct}
        args.update(instance)
        prompt_text += instance_template % args
    prompt_text += "Choose an instance: "

    def validation(input):
        choice = int(input)
        if not choice in range(1, len(env.instances) + 1):
            raise ValueError("%d is not a valid instance" % choice)
        return choice

    choice = prompt(prompt_text, validate=validation)
    env.active_instance = env.instances[choice - 1]['instance']


def run_command_on_selected_server(command):
    select_instance()
    selected_hosts = [
        'ubuntu@' + env.active_instance.public_dns_name
    ]
    execute(command, hosts=selected_hosts)


def _install_nginx():
    sudo('apt-get install nginx')
    sudo('/etc/init.d/nginx start')


def install_nginx():
    run_command_on_selected_server(_install_nginx)


def stop_instance(timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    select_instance()
    selected = env.active_instance
    waited = 0
    selected.stop()
    while (not selected.state == 'stopped') and (waited < timeout_val):
        time.sleep(wait_val)
        waited += int(wait_val)
        print "Instance {} is {}".format(selected.id, selected.state)
        selected.update()


def start_instance(timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    select_instance(state='stopped')
    selected = env.active_instance
    waited = 0
    selected.start()
    while (not selected.state == 'running') and (waited < timeout_val):
        time.sleep(wait_val)
        waited += int(wait_val)
        print "Instance {} is {}".format(selected.id, selected.state)
        selected.update()


def terminate_instance(timeout=60, interval=2):
    wait_val = int(interval)
    timeout_val = int(timeout)
    select_instance(state='stopped')
    selected = env.active_instance
    waited = 0
    selected.terminate()
    while (not selected.state == 'terminated') and (waited < timeout_val):
        time.sleep(wait_val)
        waited += int(wait_val)
        print "Instance {} is {}".format(selected.id, selected.state)
        selected.update()


def _nginx_config():
    os.system('cp simple_nginx_config_template nginx_config/simple_nginx_config')
    re = "s/xxxx/{}/g".format(env.active_instance.public_dns_name)
    complete = 'sed -i -e {} nginx_config/simple_nginx_config'.format(re)
    os.system(complete)

    upload_project(local_dir='~/projects/fabrictests/nginx_config/')
    # sudo('mv nginx_config/simple_nginx_config /etc/nginx/sites-available/default')
    # sudo('/etc/init.d/nginx restart')


def nginx_config():
    run_command_on_selected_server(_nginx_config)


def _deploy():
    upload_project(local_dir='~/projects/fabrictests/upload/')
    sudo('apt-get install supervisor')
    sudo('mv upload/supervisord.conf supervisord.conf')
    run('supervisord')

def deploy():
    run_command_on_selected_server(_deploy)
