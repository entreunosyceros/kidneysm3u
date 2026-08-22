import tkinter as tk
from tkinter import ttk, messagebox
import json
import webbrowser
import os
from ui_theme import style_window, style_listbox, set_window_icon, center_window

class EnlacesManager:
    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.title('Gestionar Enlaces')
        self.window.geometry('520x380')
        self.window.minsize(420, 300)
        style_window(self.window)
        set_window_icon(self.window)
        center_window(self.window, 520, 380)
        
        self.enlaces = self.cargar_enlaces()
        self.create_widgets()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text='Enlaces', style='PageTitle.TLabel').pack(anchor=tk.W)
        ttk.Label(
            main_frame,
            text='Accesos rápidos que aparecen en el menú',
            style='Muted.TLabel',
        ).pack(anchor=tk.W, pady=(0, 14))
        
        input_frame = ttk.Frame(main_frame, style='Card.TFrame')
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_frame, text='Nombre', style='CardMuted.TLabel').grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        ttk.Label(input_frame, text='URL', style='CardMuted.TLabel').grid(row=0, column=1, sticky=tk.W, padx=(10, 0), pady=(0, 4))
        self.nombre_entry = ttk.Entry(input_frame)
        self.nombre_entry.grid(row=1, column=0, sticky=(tk.W, tk.E))
        self.url_entry = ttk.Entry(input_frame)
        self.url_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
        input_frame.columnconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=2)
        
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(buttons_frame, text='Añadir', style='Accent.TButton', command=self.añadir_enlace).pack(side=tk.LEFT)
        ttk.Button(buttons_frame, text='Eliminar seleccionado', command=self.eliminar_enlace).pack(side=tk.LEFT, padx=8)
        
        self.enlaces_listbox = tk.Listbox(main_frame, selectmode=tk.SINGLE)
        self.enlaces_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        style_listbox(self.enlaces_listbox)
        self.enlaces_listbox.bind('<Double-Button-1>', self.abrir_enlace)
        
        self.actualizar_lista()
        
    def cargar_enlaces(self):
        try:
            if os.path.exists('enlaces.json'):
                with open('enlaces.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except:
            return {}
            
    def guardar_enlaces(self):
        with open('enlaces.json', 'w', encoding='utf-8') as f:
            json.dump(self.enlaces, f, ensure_ascii=False, indent=4)
            
    def actualizar_lista(self):
        self.enlaces_listbox.delete(0, tk.END)
        for nombre in self.enlaces.keys():
            self.enlaces_listbox.insert(tk.END, nombre)
            
    def añadir_enlace(self):
        nombre = self.nombre_entry.get().strip()
        url = self.url_entry.get().strip()
        
        if not nombre or not url:
            messagebox.showerror('Error', 'Por favor, introduce nombre y URL')
            return
            
        self.enlaces[nombre] = url
        self.guardar_enlaces()
        self.actualizar_lista()
        
        # Limpiar entradas
        self.nombre_entry.delete(0, tk.END)
        self.url_entry.delete(0, tk.END)
        
    def eliminar_enlace(self):
        seleccion = self.enlaces_listbox.curselection()
        if not seleccion:
            return
            
        nombre = self.enlaces_listbox.get(seleccion[0])
        if messagebox.askyesno('Confirmar', f'¿Estás seguro de eliminar el enlace "{nombre}"?'):
            del self.enlaces[nombre]
            self.guardar_enlaces()
            self.actualizar_lista()
            
    def abrir_enlace(self, event=None):
        seleccion = self.enlaces_listbox.curselection()
        if not seleccion:
            return
            
        nombre = self.enlaces_listbox.get(seleccion[0])
        url = self.enlaces[nombre]
        webbrowser.open(url)