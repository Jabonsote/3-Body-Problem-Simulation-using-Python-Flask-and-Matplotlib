from flask import Flask, render_template, request, send_file
import numpy as np
import h5py
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D  # Import for 3D plotting
import os

app = Flask(__name__)

# Directory to save .hdf5 files
HDF5_DIR = os.path.join(os.getcwd(), 'hdf5_files')
if not os.path.exists(HDF5_DIR):
    os.makedirs(HDF5_DIR)

def f(y, m1, m2, m3):
    r12 = np.linalg.norm(y[0:3] - y[3:6])
    r23 = np.linalg.norm(y[3:6] - y[6:9])
    r31 = np.linalg.norm(y[6:9] - y[0:3])

    # Forces
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
        # Get user inputs from the form
        num_snapshots = int(request.form['num_snapshots'])
        softening_length = float(request.form['softening_length'])

        # Parse masses
        masses = np.array([
            float(request.form['mass_1']),
            float(request.form['mass_2']),
            float(request.form['mass_3'])
        ])

        # Initial conditions
        r1 = np.array([float(request.form['pos1_x']), float(request.form['pos1_y']), float(request.form['pos1_z'])])
        r2 = np.array([float(request.form['pos2_x']), float(request.form['pos2_y']), float(request.form['pos2_z'])])
        r3 = np.array([float(request.form['pos3_x']), float(request.form['pos3_y']), float(request.form['pos3_z'])])
        v1 = np.array([float(request.form['vel1_x']), float(request.form['vel1_y']), float(request.form['vel1_z'])])
        v2 = np.array([float(request.form['vel2_x']), float(request.form['vel2_y']), float(request.form['vel2_z'])])
        v3 = np.array([float(request.form['vel3_x']), float(request.form['vel3_y']), float(request.form['vel3_z'])])

        y = np.concatenate((r1, r2, r3, v1, v2, v3))

        # Time settings
        t0 = 0.0
        tf = float(request.form['end_time'])  # End time from user input
        h = (tf - t0) / num_snapshots  # Step size
        t = t0

        # Initialize arrays to save results
        positions = np.zeros((num_snapshots, 3, 3))  # num_snapshots x 3 bodies x 3 dimensions
        velocities = np.zeros((num_snapshots, 3, 3))  # num_snapshots x 3 bodies x 3 dimensions

        # Run the simulation
        for i in range(num_snapshots):
            positions[i] = y[0:9].reshape(3, 3)  # Store the positions (x, y, z) of the three bodies
            velocities[i] = y[9:18].reshape(3, 3)  # Store the velocities (vx, vy, vz) of the three bodies
            y = rk4(t, y, h, *masses)
            t += h

        # Create an HDF5 file
        hdf5_file_path = os.path.join(HDF5_DIR, 'simulation_data.hdf5')
        with h5py.File(hdf5_file_path, 'w') as hdf:
            hdf.create_dataset('num_snapshots', data=num_snapshots)
            hdf.create_dataset('masses', data=masses)
            hdf.create_dataset('positions', data=positions)

        # Create a CSV file
        csv_file_path = os.path.join(HDF5_DIR, 'simulation_data.csv')
        with open(csv_file_path, 'w') as csvfile:
            csvfile.write("Snapshot, Body, x, y, z, vx, vy, vz\n")
            for i in range(num_snapshots):
                for j in range(3):  # 3 bodies
                    csvfile.write(f"{i}, Body {j + 1}, {positions[i][j][0]}, {positions[i][j][1]}, {positions[i][j][2]}, "
                                  f"{velocities[i][j][0]}, {velocities[i][j][1]}, {velocities[i][j][2]}\n")

        # Optional: Create video if requested
        generate_video = 'generate_video' in request.form
        video_path = None
        if generate_video:
            video_path = create_video(positions)

        return f"HDF5 file created at: {hdf5_file_path}, CSV file created at: {csv_file_path}" + (f", Video created at: {video_path}" if video_path else "")

    except Exception as e:
        return f"An error occurred: {str(e)}", 500

def create_video(positions):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')  # Create a 3D subplot
    ax.set_facecolor('black')  # Set the background color to black
    ax.set_xlim(-10, 10)
    ax.set_ylim(-10, 10)
    ax.set_zlim(-10, 10)

    # Hide the axes
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.zaxis.set_visible(False)

    # Plot initial positions
    scat = ax.scatter(positions[0, :, 0], positions[0, :, 1], positions[0, :, 2], color='white')  # Set initial point color

    def update(frame):
        ax.cla()  # Clear the axis
        ax.set_facecolor('black')  # Set the background color to black
        ax.set_xlim(-100, 100)
        ax.set_ylim(-100, 100)
        ax.set_zlim(-100, 100)
        scat = ax.scatter(positions[frame, :, 0], positions[frame, :, 1], positions[frame, :, 2], color='white')  # Update the scatter plot with new positions
        ax.set_title(f"Frame {frame}", color='white')  # Set title color to white
        ax.view_init(elev=20, azim=frame * 2)  # Adjust the view angle for better visualization

    ani = animation.FuncAnimation(fig, update, frames=positions.shape[0], repeat=False)
    video_path = os.path.join(HDF5_DIR, 'simulation_video.mp4')
    ani.save(video_path, writer='ffmpeg', fps=30)  # Save video at 30 frames per second
    plt.close(fig)

    return video_path

@app.route('/video')
def video():
    return send_file(os.path.join(HDF5_DIR, 'simulation_video.mp4'), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
