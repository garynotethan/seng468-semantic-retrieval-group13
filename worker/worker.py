import pika
import json
import os
import psycopg2
import time

DB_URL = os.environ.get('DATABASE_URL')

def process_pdf(ch, method, properties, body):
    data = json.loads(body)
    user_id = data['user_id']
    document_id = data['document_id']

    time.sleep(3)# process here
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(
            "UPDATE documents SET status = 'ready' WHERE id = %s", 
            (document_id)
        )
        conn.commit()
        cur.close()
        conn.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        print(f"error processing document")
        ch.basic_nack(delivery_tag=method.delivery_tag, multiple=False)

    
def main():
    # host should be name of rabbitmq container i think
    connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
    channel = connection.channel()

    channel.queue_declare(queue='pdf_tasks_queue', durable=True)

    # can setup stuff like prefetch, queue type args idk

    channel.basic_consume(queue='pdf_tasks_queue', on_message_callback=process_pdf)

    channel.start_consuming()



if __name__ == '__main__':
    main()

