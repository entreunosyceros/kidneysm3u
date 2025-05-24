import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import re

class M3USorter:
    def __init__(self, root, input_file):
        self.window = tk.Toplevel(root)
        self.window.title('Ordenar Lista M3U')
        self.window.geometry('800x600')
        
        self.input_file = input_file
        self.channels = []
        self.clipboard = []
        self.last_selection = None
        self.drag_start_index = None
        
        self.create_widgets()
        self.load_channels()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding='10')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Frame para búsqueda
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text='Buscar:').pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_channels)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Frame para la lista y el scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Lista de canales
        self.channels_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED)
        self.channels_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar para la lista
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.channels_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.channels_listbox.config(yscrollcommand=scrollbar.set)
        
        # Botones de edición
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        self.drag_enabled = tk.BooleanVar(value=False)
        
        ttk.Button(buttons_frame, text='Cortar (Ctrl+X)', command=self.cut_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Copiar (Ctrl+C)', command=self.copy_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Pegar (Ctrl+V)', command=self.paste_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Eliminar (Del)', command=self.delete_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Editar Canal', command=self.edit_channel).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Cambiar Grupo', command=self.change_group).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(buttons_frame, text='Activar Drag & Drop', variable=self.drag_enabled, 
                       command=self.toggle_drag_drop).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Guardar', command=self.save_channels).pack(side=tk.RIGHT, padx=5)
        
        self.window.bind('<Control-x>', lambda e: self.cut_channels())
        self.window.bind('<Control-c>', lambda e: self.copy_channels())
        self.window.bind('<Control-v>', lambda e: self.paste_channels())
        self.window.bind('<Delete>', lambda e: self.delete_channels())
        self.window.bind('<Control-a>', lambda e: self.select_all())

    def select_all(self, event=None):
        self.channels_listbox.select_set(0, tk.END)
        return 'break'

    def copy_channels(self, event=None):
        selected_indices = self.channels_listbox.curselection()
        if not selected_indices:
            return
        self.clipboard = [(self.channels[i], self.channels_listbox.get(i)) for i in selected_indices]

    def paste_channels(self):
        if not self.clipboard:
            return
            
        current_selection = self.channels_listbox.curselection()
        insert_index = current_selection[0] if current_selection else tk.END
        
        for channel, name in self.clipboard:
            if insert_index == tk.END:
                self.channels.append(channel)
                self.channels_listbox.insert(tk.END, name)
            else:
                self.channels.insert(insert_index, channel)
                self.channels_listbox.insert(insert_index, name)
                insert_index += 1

    def delete_channels(self, event=None):
        selected_indices = self.channels_listbox.curselection()
        if not selected_indices:
            return
            
        for i in reversed(selected_indices):
            self.channels.pop(i)
            self.channels_listbox.delete(i)

    def load_channels(self):
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            i = 0
            while i < len(lines):
                if lines[i].startswith('#EXTINF:'):
                    if i + 1 < len(lines):
                        self.channels.append((lines[i], lines[i + 1]))
                        self.channels_listbox.insert(tk.END, self.get_channel_name(lines[i]))
                        i += 2
                    else:
                        i += 1
                else:
                    i += 1
                    
        except Exception as e:
            messagebox.showerror('Error', f'Error al cargar el archivo: {str(e)}')
    
    def get_channel_name(self, extinf_line):
        try:
            return extinf_line.split(',')[-1].strip()
        except:
            return 'Canal sin nombre'

    def edit_channel(self):
        selection = self.channels_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        extinf_line, url_line = self.channels[index]
        
        edit_window = tk.Toplevel(self.window)
        edit_window.title('Editar Canal')
        edit_window.geometry('600x300')
        
        ttk.Label(edit_window, text='Información del canal:').pack(pady=5)
        info_text = tk.Text(edit_window, height=5)
        info_text.insert('1.0', extinf_line)
        info_text.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(edit_window, text='URL:').pack(pady=5)
        url_text = tk.Text(edit_window, height=2)
        url_text.insert('1.0', url_line)
        url_text.pack(fill=tk.X, padx=5, pady=5)
        
        def save_changes():
            new_extinf = info_text.get('1.0', 'end-1c')
            new_url = url_text.get('1.0', 'end-1c')
            self.channels[index] = (new_extinf + '\n', new_url + '\n')
            self.channels_listbox.delete(index)
            self.channels_listbox.insert(index, self.get_channel_name(new_extinf))
            edit_window.destroy()
            
        ttk.Button(edit_window, text='Guardar', command=save_changes).pack(pady=10)

    def save_channels(self):
        output_file = filedialog.asksaveasfilename(
            defaultextension='.m3u',
            filetypes=[('Archivos M3U', '*.m3u')],
            initialfile='lista_ordenada.m3u'
        )
        
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('#EXTM3U\n')
                    for extinf_line, url_line in self.channels:
                        f.write(extinf_line)
                        f.write(url_line)
                messagebox.showinfo('Éxito', 'Lista guardada correctamente')
                self.window.destroy()
            except Exception as e:
                messagebox.showerror('Error', f'Error al guardar el archivo: {str(e)}')

    def toggle_drag_drop(self):
        if self.drag_enabled.get():
            self.channels_listbox.bind('<Button-1>', self.on_click)
            self.channels_listbox.bind('<B1-Motion>', self.on_drag)
            self.channels_listbox.bind('<ButtonRelease-1>', self.on_drop)
        else:
            self.channels_listbox.unbind('<Button-1>')
            self.channels_listbox.unbind('<B1-Motion>')
            self.channels_listbox.unbind('<ButtonRelease-1>')
            
    def on_click(self, event):
        self.drag_start_index = self.channels_listbox.nearest(event.y)
        
    def on_drag(self, event):
        drag_index = self.channels_listbox.nearest(event.y)
        if drag_index != self.drag_start_index:
            self.move_channels(self.drag_start_index, drag_index)
            self.drag_start_index = drag_index

    def on_drop(self, event):
        pass  

    def move_channels(self, from_index, to_index):
        selected_indices = self.channels_listbox.curselection()
        if not selected_indices:
            selected_indices = [from_index]
            
        selected_channels = [self.channels[i] for i in selected_indices]
        selected_names = [self.channels_listbox.get(i) for i in selected_indices]
        
        for i in reversed(selected_indices):
            self.channels.pop(i)
            self.channels_listbox.delete(i)
        
        for i, (channel, name) in enumerate(zip(selected_channels, selected_names)):
            insert_pos = to_index if to_index < from_index else to_index - len(selected_indices) + 1
            self.channels.insert(insert_pos + i, channel)
            self.channels_listbox.insert(insert_pos + i, name)
            self.channels_listbox.selection_set(insert_pos + i)

    def cut_channels(self):
        self.copy_channels()
        self.delete_channels()

    def change_group(self):
        selected_indices = self.channels_listbox.curselection()
        if not selected_indices:
            return
            
        new_group = simpledialog.askstring("Cambiar Grupo", "Ingrese el nuevo grupo:")
        if new_group:
            for i in selected_indices:
                extinf_line, url = self.channels[i]
                updated_line = re.sub(
                    r'(group-title=")[^"]*(")',
                    f'\\1{new_group}\\2',
                    extinf_line,
                    flags=re.IGNORECASE
                )
                if 'group-title=' not in updated_line:
                    updated_line = extinf_line.replace('#EXTINF:', f'#EXTINF: group-title="{new_group}",', 1)
                
                self.channels[i] = (updated_line, url)
                self.channels_listbox.delete(i)
                self.channels_listbox.insert(i, self.get_channel_name(updated_line))

    def filter_channels(self, *args):
        search_term = self.search_var.get().lower()
        self.channels_listbox.delete(0, tk.END)
        
        for i, (extinf_line, _) in enumerate(self.channels):
            channel_name = self.get_channel_name(extinf_line)
            if search_term in channel_name.lower():
                self.channels_listbox.insert(tk.END, channel_name)