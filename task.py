from kubernetes import client, config
from google.cloud import storage
import jenkins
import time
import os

####################################################################################################
bucket_name = 'automatictrainingcicd-aiplatform'
model_name = 'best_model.hdf5'
####################################################################################################


def clean_jobs():
    #config.load_kube_config('config.yaml')
    config.load_kube_config()

    api_instance=client.BatchV1Api()
    print("Listing jobs:")
    api_response = api_instance.list_job_for_all_namespaces()
    jobs = []
    print('job-name  job-namespace  active  succeeded  failed  start-time  completion-time')
    for i in api_response.items:
        jobs.append([i.metadata.name,i.metadata.namespace])
        print("%s  %s  %s  %s  %s  %s  %s" % (i.metadata.name,i.metadata.namespace,i.status.active,i.status.succeeded,i.status.failed,i.status.start_time,i.status.completion_time))
    print('Deleting jobs...')
    if len(jobs) > 0:
        for i in range(len(jobs)):
            api_instance.delete_namespaced_job(jobs[i][0],jobs[i][1])
        print("Jobs deleted.")
    else:
        print("No jobs found.")
    return

def model_to_production():
    storage_client = storage.Client.from_service_account_json('AutomaticTrainingCICD-68f56bfa992e.json')
    bucket = storage_client.bucket(bucket_name)
    status = storage.Blob(bucket=bucket, name='{}/{}'.format('testing',model_name)).exists(storage_client)
    if status == True:
        print('Copying model...')
        source_blob = bucket.blob('{}/{}'.format('testing',model_name))
        destination_blob_name = '{}/{}'.format('production',model_name)
        blob_copy = bucket.copy_blob(source_blob, bucket, destination_blob_name)
        print('Model from testing registry has been copied to production registry.')
    else:
        print('No model found at testing registry.')
    return

def check_services():
    api_instance = client.CoreV1Api()
    api_response = api_instance.list_service_for_all_namespaces()
    print('Listing services:')
    print('service-namespace  service-name')
    services = []
    for i in api_response.items:
        print("%s  %s" % (i.metadata.namespace, i.metadata.name))
        services.append(i.metadata.name)
    if True in (t.startswith('gke-api') for t in services): 
        print('gke-api service is active. Proceeding to systematically shutdown its pods...')
        shutdown_pods()
        return
    else:
        jenkins_build()
        return

def shutdown_pods():
    #config.load_kube_config('config.yaml')
    config.load_kube_config()
    api_instance = client.CoreV1Api()
    print("Listing pods:")
    api_response = api_instance.list_pod_for_all_namespaces(watch=False)
    pods = []
    print('pod-ip-address  pod-namespace  pod-name')
    for i in api_response.items:
        print("%s  %s  %s" % (i.status.pod_ip, i.metadata.namespace, i.metadata.name))
        pods.append([i.metadata.name, i.metadata.namespace])
    print('Shutting down pods...')
    print('Deleting only gke-api pods...')
    if len(pods) > 0:
        for i in range(len(pods)):
            if pods[i][0].startswith('gke-api') == True:
                api_instance.delete_namespaced_pod(pods[i][0],pods[i][1])
                print("Pod '{}' shut down.".format(pods[i][0]))
                time.sleep(120)
        print("All pods have been shut down.")
    else:
        print("No pods found.")
    return

def jenkins_build():
    print('gke-api service is not active. Proceeding to build AutomaticTraining-PredictionAPI job at Jenkins.')
    server = jenkins.Jenkins('http://localhost:8080', username='your_username', password='your_password')
    server.build_job('AutomaticTraining-PredictionAPI')
    print('AutomaticTraining-PredictionAPI job has been triggered, check Jenkins logs for more information.')
    return

def main():
    clean_jobs()
    model_to_production()
    check_services()

if __name__ == '__main__':
    main()

    

