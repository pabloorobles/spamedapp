"""Interfaz de Spamed Travel.

A diferencia de core, aca NO se importan los submodulos al cargar el paquete:
cada vista se importa cuando hace falta, y ademas todos dependen de que exista
una QApplication. La resolucion correcta de estos imports se garantiza desde
el .spec, con collect_submodules.
"""
