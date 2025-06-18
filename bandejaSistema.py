import pystray
from PIL import Image
import tkinter as tk
from pathlib import Path

class IconoBandeja:
    def __init__(self, root):
        self.root = root
        self.oculto = False
        self._last_click_time = 0
        
        # Intentar cargar el icono pequeño optimizado
        small_icon_path = Path(__file__).parent / "img" / "logo_small.png"
        icon_path = Path(__file__).parent / "img" / "logo.png"
        
        try:
            self.image = Image.open(str(small_icon_path))
        except (FileNotFoundError, IOError):
            # Si no existe el icono pequeño, cargar y redimensionar el grande
            self.image = Image.open(str(icon_path))
            self.image = self.image.resize((24, 24), Image.Resampling.LANCZOS)
        
        # Asegurar que la imagen tenga canal alfa (transparencia)
        if self.image.mode != 'RGBA':
            self.image = self.image.convert('RGBA')
            
        # Optimizar el icono para temas claros y oscuros
        self.image_clara = self.optimizar_icono_claro()
        self.image_oscura = self.optimizar_icono_oscuro()
        
        # Crear el menú del ícono con tooltip
        self.icon = pystray.Icon(
            "Kidneys M3U/M3U8",
            self.image_clara,  # Comenzar con el icono claro
            menu=self.crear_menu(),
            title="Kidneys M3U/M3U8"  # Tooltip al pasar el mouse
        )
        
        # Agregar manejador de doble clic para restaurar ventana
        self.icon.on_double_click = self.restaurar_ventana
        # No asignar self.icon.on_click para no interferir con el menú contextual
        # self.icon.on_click = self.on_icon_click  # ¡NO USAR!
        
        # Iniciar el icono en un hilo separado
        import threading
        self.icon_thread = threading.Thread(target=self.icon.run)
        self.icon_thread.daemon = True
        self.icon_thread.start()
        
        # Configurar el comportamiento de la ventana principal
        self.root.protocol('WM_DELETE_WINDOW', self.minimizar_a_bandeja)
        
    def optimizar_icono_claro(self):
        """Genera una versión clara del icono para temas claros"""
        imagen = self.image.convert('RGBA')
        datos = imagen.getdata()
        nuevos_datos = []
        for item in datos:
            r, g, b, a = item
            # Hacer el icono más oscuro manteniendo la transparencia
            factor = 0.8
            nuevos_datos.append((
                max(0, int(r * factor)),
                max(0, int(g * factor)), 
                max(0, int(b * factor)),
                a
            ))
        imagen.putdata(nuevos_datos)
        return imagen
        
    def optimizar_icono_oscuro(self):
        """Genera una versión brillante del icono para temas oscuros"""
        imagen = self.image.convert('RGBA') 
        datos = imagen.getdata()
        nuevos_datos = []
        for item in datos:
            r, g, b, a = item
            # Hacer el icono más brillante manteniendo la transparencia
            factor = 1.5
            nuevos_datos.append((
                min(255, int(r * factor)),
                min(255, int(g * factor)),
                min(255, int(b * factor)),
                a
            ))
        imagen.putdata(nuevos_datos)
        return imagen

    def crear_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                "Restaurar",
                self.restaurar_ventana,
                default=True  # Esta opción se ejecuta al hacer doble clic
            ),
            pystray.MenuItem(
                "Salir",
                self.salir_programa
            )
        )
    
    def minimizar_a_bandeja(self):
        """Oculta la ventana principal"""
        self.root.withdraw()  # Ocultar la ventana principal
        self.oculto = True
    
    def restaurar_ventana(self, icon, item):
        """Restaura la ventana principal desde la bandeja"""
        self.root.after(0, self.mostrar_ventana)  # Programar la restauración de la ventana
    
    def mostrar_ventana(self):
        """Muestra la ventana principal"""
        self.root.deiconify()  # Mostrar la ventana
        self.root.lift()  # Traer al frente
        self.root.focus_force()  # Dar foco
        self.oculto = False
    
    def salir_programa(self, icon, item):
        """Cierra completamente el programa"""
        def cerrar():
            self.icon.stop()  # Detener el ícono de la bandeja
            self.root.quit()  # Cerrar la aplicación
        
        self.root.after(0, cerrar)  # Ejecutar el cierre en el hilo principal
    
    def esta_oculto(self):
        """Retorna True si la ventana está minimizada en la bandeja"""
        return self.oculto
    
    def actualizar_tema(self, tema_oscuro=False):
        """Actualiza el icono según el tema actual"""
        if tema_oscuro:
            self.icon.icon = self.image_oscura
        else:
            self.icon.icon = self.image_clara
