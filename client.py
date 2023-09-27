import socket
import os
import wx
import zipfile

HOST = '127.0.0.1'
PORT_META = 8000
PORT_DATA = 8001
DOWNLOAD_FOLDER = 'downloads/'

class FileTransferClient(wx.Frame):
    def __init__(self, parent, title):
        super(FileTransferClient, self).__init__(parent, title=title, size=(500, 500))
        self.InitUI()

    def InitUI(self):
        # Create panel of at least 500x500 pixels and centered on the screen
        panel = wx.Panel(self, size=(700, 500), pos=(0, 0))
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        self.listbox = wx.ListBox(panel)
        vbox.Add(self.listbox, 1, flag=wx.EXPAND)
        
        # Create context menu
        self.popupMenu = wx.Menu()
        downloadItem = self.popupMenu.Append(-1, 'Descargar')
        renameItem = self.popupMenu.Append(-1, 'Renombrar')
        deleteItem = self.popupMenu.Append(-1, 'Eliminar')
        copyItem = self.popupMenu.Append(-1, 'Copiar')
        
        self.Bind(wx.EVT_MENU, self.download_file, downloadItem)
        self.Bind(wx.EVT_MENU, self.rename_file, renameItem)
        self.Bind(wx.EVT_MENU, self.delete_file, deleteItem)
        self.Bind(wx.EVT_MENU, self.copy_file, copyItem)
        self.listbox.Bind(wx.EVT_CONTEXT_MENU, self.showPopupMenu)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        btn_upload = wx.Button(panel, label='Subir archivo', size=(200, 30))
        btn_upload.Bind(wx.EVT_BUTTON, self.upload_file)

        btn_folder_upload = wx.Button(panel, label='Subir carpeta', size=(200, 30))
        btn_folder_upload.Bind(wx.EVT_BUTTON, self.upload_folder)
        
        btn_exit = wx.Button(panel, label='Salir', size=(200, 30))
        btn_exit.Bind(wx.EVT_BUTTON, self.exit_app)
        
        hbox.Add(btn_upload)
        hbox.Add(btn_exit)
        hbox.Add(btn_folder_upload)
        
        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)
        
        panel.SetSizer(vbox)

        self.list_remote_files(self)

    def showPopupMenu(self, event):
        pos = self.listbox.ScreenToClient(event.GetPosition())
        self.listbox.PopupMenu(self.popupMenu, pos)
    
    def copy_file(self, event):
        selected_file = self.listbox.GetString(self.listbox.GetSelection())
        if selected_file:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT_META))
                s.send(f'COPY_REMOTE|{selected_file}'.encode())
        self.list_remote_files(self)
    
    def upload_folder(self, event):
        with wx.DirDialog(self, "Elige una carpeta", style=wx.DD_DEFAULT_STYLE) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return
            if dirname := dirDialog.GetPath():
                os.chdir(os.path.dirname(dirname))
                zipname = f'{os.path.basename(dirname)}_serverzipped.zip'
                with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                    for foldername, subfolders, filenames in os.walk(os.path.basename(dirname)):
                        for file in filenames:
                            zip_ref.write(os.path.join(foldername, file))
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((HOST, PORT_META))
                    s.send(f'UPLOAD_FOLDER|{zipname}'.encode())
                    response = s.recv(1024).decode()
                    if response == 'READY_TO_RECEIVE':
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ds:
                            ds.connect((HOST, PORT_DATA))
                            with open(zipname, 'rb') as f:
                                data = f.read(1024)
                                while data:
                                    ds.send(data)
                                    data = f.read(1024)
                os.remove(zipname)
        self.list_remote_files(self)

    def list_remote_files(self, event):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT_META))
            s.send('LIST_REMOTE'.encode())
            files = s.recv(1024).decode().split(',')
            self.listbox.Clear()
            for file in files:
                self.listbox.Append(file)

    def upload_file(self, event):
        with wx.FileDialog(self, "Elige un archivo", wildcard="All files (*.*)|*.*", style=wx.FD_OPEN) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            if filepath := fileDialog.GetPath():
                filename = os.path.basename(filepath)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((HOST, PORT_META))
                    s.send(f'UPLOAD_FILE|{filename}'.encode())
                    response = s.recv(1024).decode()
                    if response == 'READY_TO_RECEIVE':
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ds:
                            ds.connect((HOST, PORT_DATA))
                            with open(filepath, 'rb') as f:
                                while data := f.read(1024):
                                    ds.send(data)
        self.list_remote_files(self)

    def download_file(self, event):
        if not (
            selected_file := self.listbox.GetString(self.listbox.GetSelection())
        ):
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT_META))
            s.send(f'DOWNLOAD_FILE|{selected_file}'.encode())
            response, filename = s.recv(1024).decode().split('|')
            if response.startswith('READY_TO_SEND'):
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ds:
                    ds.connect((HOST, PORT_DATA))
                    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                    with open(filepath, 'wb') as f:
                        while data := ds.recv(1024):
                            f.write(data)
                if filename.endswith('_serverzipped.zip'):
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        zip_ref.extractall(DOWNLOAD_FOLDER)
                    os.remove(filepath)
        # when the file is finished downloading, show a message box
        wx.MessageBox(f'Archivo {filename} descargado en {DOWNLOAD_FOLDER}', 'Descarga finalizada', wx.OK | wx.ICON_INFORMATION)

    def rename_file(self, event):
        selected_file = self.listbox.GetString(self.listbox.GetSelection())
        if selected_file:
            renameDialog = wx.TextEntryDialog(self, 'Nuevo nombre:', 'Renombrar archivo', selected_file)
            if renameDialog.ShowModal() == wx.ID_OK:
                new_name = renameDialog.GetValue()
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((HOST, PORT_META))
                    s.send(f'RENAME_REMOTE|{selected_file}|{new_name}'.encode())
        self.list_remote_files(self)

    def delete_file(self, event):
        selected_file = self.listbox.GetString(self.listbox.GetSelection())
        if selected_file:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT_META))
                s.send(f'DELETE_REMOTE|{selected_file}'.encode())
        self.list_remote_files(self)

    def exit_app(self, event):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT_META))
            s.send('EXIT'.encode())
        self.Close()

if __name__ == '__main__':
    app = wx.App()
    frame = FileTransferClient(None, title='Cliente de Transferencia de Archivos')
    frame.Show()
    app.MainLoop()

