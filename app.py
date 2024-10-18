from flask import Flask, render_template, request, send_file
import numpy as np
import h5py
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D  # Import for 3D plotting
import os

app = Flask(__name__)

# Directorio para guardar los archivos .hdf5
HDF5_DIR = os.path.join(os.getcwd(), 'hdf5_files')
if not os.path.exists(HDF5_DIR):
    os.makedirs(HDF5_DIR)

def f(y, m1, m2, m3):
    r12 = np.linalg.norm(y[0:3] - y[3:6])
    r23 = np.linalg.norm(y[3:6] - y[6:9])
    r31 = np.linalg.norm(y[6:9] - y[0:3])

    # Fuerzas
    f1 = m2 * (y[3:6] - y[0:3]) / r12**3 + m3 * (y[6:9] - y[0:3]) / r31**3
    f2 = m1 * (y[0:3] - y[3:6]) / r12**3 + m3 * (y[6:9] - y[3:6]) / r23**3
    f3 = m1 * (y[0:3] - y[6:9]) / r31**3 + m2 * (y[3:6] - y[6:9]) / r23**3

    return np.concatenate((y[9:18], f1, f2, f3))

def rk4(t, y, h, m1, m2, m3):
    k1 = h * f(y, m1, m2, m3)
    k2 = h * f(y + k1 / 2, m1, m2, m3)
    k3 = h * f(y + k2 / 2, m1, m2, m3)
    k4 = h * f(y + k3, m1, m2, m3)
    return y + (k1 + 2 * k2 + 2 * k3 + k4) / 6

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        # Obtener las entradas del usuario
        num_snapshots = int(request.form['num_snapshots'])
        softening_length = float(request.form['softening_length'])

        # Parsear masas
        masses = np.array([
            float(request.form['mass_1']),
            float(request.form['mass_2']),
            float(request.form['mass_3'])
        ])

        # Condiciones iniciales
        r1 = np.array([float(request.form['pos1_x']), float(request.form['pos1_y']), float(request.form['pos1_z'])])
        r2 = np.array([float(request.form['pos2_x']), float(request.form['pos2_y']), float(request.form['pos2_z'])])
        r3 = np.array([float(request.form['pos3_x']), float(request.form['pos3_y']), float(request.form['pos3_z'])])
        v1 = np.array([float(request.form['vel1_x']), float(request.form['vel1_y']), float(request.form['vel1_z'])])
        v2 = np.array([float(request.form['vel2_x']), float(request.form['vel2_y']), float(request.form['vel2_z'])])
        v3 = np.array([float(request.form['vel3_x']), float(request.form['vel3_y']), float(request.form['vel3_z'])])

        y = np.concatenate((r1, r2, r3, v1, v2, v3))

        # Configuración de tiempo
        t0 = 0.0
        tf = float(request.form['end_time'])
        h = (tf - t0) / num_snapshots
        t = t0

        # Inicializar arrays para guardar los resultados
        positions = np.zeros((num_snapshots, 3, 3))  # num_snapshots x 3 cuerpos x 3 dimensiones
        velocities = np.zeros((num_snapshots, 3, 3))  # num_snapshots x 3 cuerpos x 3 dimensiones

        # Ejecutar la simulación
        for i in range(num_snapshots):
            positions[i] = y[0:9].reshape(3, 3)
            velocities[i] = y[9:18].reshape(3, 3)
            y = rk4(t, y, h, *masses)
            t += h

        # Crear archivo HDF5
        hdf5_file_path = os.path.join(HDF5_DIR, 'simulation_data.hdf5')
        with h5py.File(hdf5_file_path, 'w') as hdf:
            hdf.create_dataset('num_snapshots', data=num_snapshots)
            hdf.create_dataset('masses', data=masses)
            hdf.create_dataset('positions', data=positions)

        # Crear archivo CSV
        csv_file_path = os.path.join(HDF5_DIR, 'simulation_data.csv')
        with open(csv_file_path, 'w') as csvfile:
            csvfile.write("Snapshot, Body, x, y, z, vx, vy, vz\n")
            for i in range(num_snapshots):
                for j in range(3):
                    csvfile.write(f"{i}, Body {j + 1}, {positions[i][j][0]}, {positions[i][j][1]}, {positions[i][j][2]}, "
                                  f"{velocities[i][j][0]}, {velocities[i][j][1]}, {velocities[i][j][2]}\n")

        # Crear video si se solicita
        generate_video = 'generate_video' in request.form
        video_path = None
        if generate_video:
            video_path = create_video(positions, velocities)

        return f"Archivo HDF5 creado en: {hdf5_file_path}, Archivo CSV creado en: {csv_file_path}" + (f", Video creado en: {video_path}" if video_path else "")

    except Exception as e:
        return f"Se produjo un error: {str(e)}", 500

def create_video(positions, velocities):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor('black')

    # Limpiar ejes
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.zaxis.set_visible(False)

    # Definir colores neón para las partículas
    neon_colors = ['cyan', 'magenta', 'yellow']

    # Trazar las posiciones iniciales y las trayectorias
    scat = ax.scatter(positions[0, :, 0], positions[0, :, 1], positions[0, :, 2], color=neon_colors)

    # Guardar trayectorias
    trajectories = [ax.plot([], [], [], lw=1, color=color)[0] for color in neon_colors]

    # Rango dinámico para el zoom
    dynamic_limit = np.max(np.abs(positions)) * 1.2

    # Crear un texto en la esquina inferior izquierda (small font)
    text_box = fig.text(0.4, 0.15, '', fontsize=5, color='white', ha='left', va='bottom')

    def update(frame):
        ax.cla()  # Limpiar el gráfico
        ax.set_facecolor('black')  # Fondo negro
        current_limit = max(np.max(np.abs(positions[frame])), 1) * 1.2

        ax.set_xlim(-current_limit, current_limit)
        ax.set_ylim(-current_limit, current_limit)
        ax.set_zlim(-current_limit, current_limit)

        # Actualizar partículas con colores neón
        for i in range(3):
            ax.scatter(positions[frame, i, 0], positions[frame, i, 1], positions[frame, i, 2], color=neon_colors[i], s=100)

        # Dibujar trayectorias
        for i, traj in enumerate(trajectories):
            traj.set_data(positions[:frame, i, 0], positions[:frame, i, 1])
            traj.set_3d_properties(positions[:frame, i, 2])
            ax.add_line(traj)

        # Vista de la cámara
        ax.view_init(elev=20, azim=frame * 2)

        # Actualizar texto de las posiciones y velocidades
        body_info = []
        for j in range(3):
            body_info.append(
                f"Body {j + 1}: Pos({positions[frame, j, 0]:.2f}, {positions[frame, j, 1]:.2f}, {positions[frame, j, 2]:.2f}) "
                f"Vel({velocities[frame, j, 0]:.2f}, {velocities[frame, j, 1]:.2f}, {velocities[frame, j, 2]:.2f})"
            )
        text_box.set_text('\n'.join(body_info))

    video_path = os.path.join(HDF5_DIR, 'simulation_video.mp4')

    try:
        ani = animation.FuncAnimation(fig, update, frames=positions.shape[0], repeat=False)
        ani.save(video_path, writer='ffmpeg', fps=30)
        print(f"Video guardado en: {video_path}")
    except Exception as e:
        print(f"Error al guardar el video: {str(e)}")
        return None

    plt.close(fig)
    return video_path





@app.route('/video')
def video():
    return send_file(os.path.join(HDF5_DIR, 'simulation_video.mp4'), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
