import pika
import json

def process_pdf(ch, method, properties, body):
    data = json.loads(body)
    user_id = data['user_id']
    document_id = data['document_id']
    


def main():
    # host should be name of rabbitmq container i think
    connection = pika.BlockingConnection(pika.ConnectoinParameters(host='rabbitmq'))
    channel = connection.channel()

    channel.queue.declare(queue='pdf_tasks_queue', durable=True)

    # can setup stuff like prefetch, queue type args idk

    channel.basic_consume(queue='pdf_tasks_queue', on_message_callback=process_pdf)

    channel.start_consuming()



if __name__ == '__main__':
    main():

