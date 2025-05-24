import tkinter as tk
from tkinter import ttk, messagebox
import json
import webbrowser
import os

class EnlacesManager:
    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.title('Gestionar Enlaces')
        self.window.geometry('400x300')
        
        self.enlaces = self.cargar_enlaces()
        self.create_widgets()
        
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.window, padding='10')
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Entrada para nuevo enlace
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(input_frame, text='Nombre:').pack(side=tk.LEFT, padx=5)
        self.nombre_entry = ttk.Entry(input_frame, width=20)
        self.nombre_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(input_frame, text='URL:').pack(side=tk.LEFT, padx=5)
        self.url_entry = ttk.Entry(input_frame, width=30)
        self.url_entry.pack(side=tk.LEFT, padx=5)
        
        # Botones de acción
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(buttons_frame, text='Añadir', command=self.añadir_enlace).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text='Eliminar Seleccionado', command=self.eliminar_enlace).pack(side=tk.LEFT, padx=5)
        
        # Lista de enlaces
        self.enlaces_listbox = tk.Listbox(main_frame, selectmode=tk.SINGLE)
        self.enlaces_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.enlaces_listbox.bind('<Double-Button-1>', self.abrir_enlace)
        
        # Cargar enlaces existentes
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