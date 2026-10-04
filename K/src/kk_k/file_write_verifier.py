"""Strict verifier for bounded file-write receipts."""


class FileWriteVerifyError(ValueError):
    pass


def verify_file_write_receipt(receipt):
    if not isinstance(receipt, dict):
        raise FileWriteVerifyError("invalid receipt")
    if receipt.get("outcome") == "VETO":
        return False
    ev = receipt.get("evidence")
    if receipt.get("outcome") != "EXECUTED" or not isinstance(ev, dict):
        raise FileWriteVerifyError("invalid outcome")
    if set(ev) != {"kind", "file"} or ev.get("kind") != "FILE_WRITE":
        raise FileWriteVerifyError("invalid evidence")
    f = ev["file"]
    req = {"schema", "path", "bytes", "sha256", "created"}
    if not isinstance(f, dict) or set(f) != req or f.get("schema") != "F.TOOL.FILE_WRITE.1":
        raise FileWriteVerifyError("invalid payload")
    if not isinstance(f.get("path"), str) or not f["path"].startswith("/root/K/K/workspace/"):
        raise FileWriteVerifyError("invalid path")
    if type(f.get("bytes")) is not int or not 0 <= f["bytes"] <= 16384:
        raise FileWriteVerifyError("invalid size")
    h = f.get("sha256")
    if not isinstance(h, str) or len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise FileWriteVerifyError("invalid digest")
    if f.get("created") is not True:
        raise FileWriteVerifyError("invalid create flag")
    return True
