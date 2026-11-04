import argparse
from getpass import getpass

from app.modules.delivery.grpc_client import DeliveryGrpcClient


def main():
    parser = argparse.ArgumentParser(description="Подписка на статусы доставки")
    parser.add_argument("delivery_id", type=int)
    args = parser.parse_args()
    token = getpass("Access token: ")
    with_client = DeliveryGrpcClient(token)
    try:
        for status in with_client.track_delivery(args.delivery_id):
            print(status["status"], flush=True)
    finally:
        with_client.close()


if __name__ == "__main__":
    main()
