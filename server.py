import shutil
import socket
import os
import zipfile

HOST = '127.0.0.1'
PORT_META = 8000
PORT_DATA = 8001
REMOTE_FOLDER = 'remote_folder/'

def handle_client_meta(conn):
    while True:
        cmd = conn.recv(1024).decode()
        if not cmd:
            break

        if cmd == 'LIST_REMOTE':
            files = os.listdir(REMOTE_FOLDER) or ['']
            conn.send(','.join(files).encode())

        elif cmd.startswith('UPLOAD_FILE') or cmd.startswith('UPLOAD_FOLDER'):
            _, filename = cmd.split('|')
            conn.send('READY_TO_RECEIVE'.encode())
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ds:
                init_data_stream(ds)
                data_conn, _ = ds.accept()
                with data_conn:
                    with open(os.path.join(REMOTE_FOLDER, filename), 'wb') as f:
                        while (data := data_conn.recv(1024)):
                            f.write(data)
                data_conn.close()
            ds.close()

            if filename.endswith('_serverzipped.zip'):
                with zipfile.ZipFile(os.path.join(REMOTE_FOLDER, filename), 'r') as zip_ref:
                    zip_ref.extractall(REMOTE_FOLDER)
                os.remove(os.path.join(REMOTE_FOLDER, filename))

        elif cmd.startswith('DOWNLOAD_FILE'):
            _, filename = cmd.split('|')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ds:
                init_data_stream(ds)
                server_path = os.path.join(REMOTE_FOLDER, filename)
                is_folder = os.path.isdir(server_path)
                if is_folder:
                    os.chdir(REMOTE_FOLDER)
                    zipname = f'{filename}_serverzipped.zip'
                    with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                        for foldername, subfolders, filenames in os.walk(filename):
                            for file in filenames:
                                zip_ref.write(os.path.join(foldername, file))
                    server_path = zipname
                conn.send(f'READY_TO_SEND|{os.path.basename(server_path)}'.encode())
                data_conn, _ = ds.accept()
                with data_conn:
                    with open(server_path, 'rb') as f:
                        while (data := f.read(1024)):
                            data_conn.send(data)
                data_conn.close()
                if is_folder:
                    os.remove(server_path)

        elif cmd.startswith('DELETE_REMOTE'):
            _, filename = cmd.split('|')
            if os.path.isdir(os.path.join(REMOTE_FOLDER, filename)):
                shutil.rmtree(os.path.join(REMOTE_FOLDER, filename))
            else:
                os.remove(os.path.join(REMOTE_FOLDER, filename))
            conn.send('FILE_DELETED'.encode())

        elif cmd.startswith('RENAME_REMOTE'):
            _, old_name, new_name = cmd.split('|')
            os.rename(os.path.join(REMOTE_FOLDER, old_name), os.path.join(REMOTE_FOLDER, new_name))
            conn.send('FILE_RENAMED'.encode())


# TODO Rename this here and in `handle_client_meta`
def init_data_stream(ds):
    ds.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ds.bind((HOST, PORT_DATA))
    ds.listen()

def start_server():
    if not os.path.exists(REMOTE_FOLDER):
        os.mkdir(REMOTE_FOLDER)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT_META))
        s.listen()
        print(f"Server started at {HOST}:{PORT_META}")
        while True:
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                handle_client_meta(conn)

if __name__ == "__main__":
    start_server()
