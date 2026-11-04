from pathlib import Path

from grpc_tools import protoc


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "proto" / "delivery.proto"
    result = protoc.main(
        [
            "grpc_tools.protoc",
            f"-I{source.parent}",
            f"--python_out={root}",
            f"--grpc_python_out={root}",
            str(source),
        ]
    )
    if result:
        raise SystemExit(result)
    for name in ("delivery_pb2.py", "delivery_pb2_grpc.py"):
        path = root / name
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text(
            "".join(line for line in lines if not line.lstrip().startswith("#")),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
