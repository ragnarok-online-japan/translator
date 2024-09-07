import re


def encode(byte_data):
    if len(byte_data) % 2 != 0:
        byte_data += b'\x00'

    # バイトデータを2バイトずつに分割してエンコード
    encoded_str = ""
    for i in range(0, len(byte_data), 2):
        two_bytes = byte_data[i:i+2]
        # 2バイトを整数に変換
        number = int.from_bytes(two_bytes, 'big')

        # サロゲートペア範囲を避けるために条件を追加
        if 0xD800 <= number <= 0xDFFF:
            number += 0x800  # サロゲートペア範囲を避ける

        # その数値を16ビットの範囲でUnicodeに変換
        encoded_str += chr(number)

    # URLセーフにするために、特殊文字を置換
    encoded_str = re.sub(r'[+/=]', lambda x: {'+': '-', '/': '_', '=': ''}[x.group(0)], encoded_str)

    return encoded_str

def decode(encoded_str):
    # URLセーフエンコードされた文字列を元に戻す
    encoded_str = encoded_str.replace('-', '+').replace('_', '/')

    byte_data = bytearray()

    # エンコードされた文字列を2バイトごとにデコード
    for char in encoded_str:
        number = ord(char)

        # サロゲートペア範囲を避けるために元の値に戻す
        if 0xD800 <= number <= 0xDFFF:
            number -= 0x800

        # 数値を2バイトのバイナリに変換
        byte_data.extend(number.to_bytes(2, 'big'))

    # 末尾に余分なnullバイトが追加されていたら削除
    if byte_data[-1] == 0:
        byte_data = byte_data[:-1]

    return bytes(byte_data)
