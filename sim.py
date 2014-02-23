from ode import (
    World, GeomPlane, Space, JointGroup, collide, ContactJoint
)

from visual import rate, box, scene
from pid import PID
from quad import Quad
from utils import set_wii_remote

class Stable(object):

    def __init__(self, quad, max_force=10, min_force=0.02):
        self.quad = quad
        # set max and min forces
        self.max_force = max_force
        self.min_force = min_force
        # commands
        self.command_pitch = 0
        self.command_roll = 0
        self.command_yaw = 0
        self.command_acceleration = 0

        # acceleration set points
        self.set_point_acceleration = 0
        self.acceleration = PID(4, 0.8, 2)
        self.acceleration.setPoint(self.set_point_acceleration)
        # Pitch set point
        self.set_point_pitch = 0
        self.pitch = PID(0.02, 0.001, 0.10)
        self.pitch.setPoint(self.set_point_pitch)
        # Roll set point
        self.set_point_roll = 0
        self.roll = PID(0.02, 0.001, 0.10)
        self.roll.setPoint(self.set_point_roll)
        # Yaw set point
        self.lock_yaw = True
        self.set_point_yaw = 90
        self.yaw = PID(0.2, 0.001, 1)
        self.yaw.setPoint(self.set_point_yaw)

    def update_forces(self, forces):
        # Update forces in min and max values
        for i, force in enumerate(forces):
            force = max(self.min_force, force)
            force = min(self.max_force, force)
            forces[i] = force
        # set values to quad
        self.quad.motors_force = forces

    def stabilize(self):
        forces = [0, 0, 0, 0]
        # acceleration
        aforce = self.acceleration.update(self.quad.vel[1])
        forces = [aforce, aforce, aforce, aforce]
        # pitch
        pforce = self.pitch.update(self.quad.pitch)
        forces[0] += pforce
        forces[1] -= pforce
        # roll
        rforce = self.roll.update(self.quad.roll)
        forces[3] += rforce
        forces[2] -= rforce
        # yaw
        if self.lock_yaw:
            yforce = self.yaw.update(self.quad.yaw)
            forces[0] += yforce
            forces[1] += yforce
            forces[2] -= yforce
            forces[3] -= yforce

        self.update_forces(forces)

    def apply_commands(self):
        if self.lock_yaw and self.command_yaw:
            self.lock_yaw = False
        if not self.command_yaw and not self.lock_yaw:
            self.set_point_yaw = self.quad.yaw
            self.yaw.setPoint(self.set_point_yaw)
            self.lock_yaw = True


        if self.set_point_acceleration != self.command_acceleration:
            self.set_point_acceleration = -self.command_acceleration
            self.acceleration.setPoint(self.set_point_acceleration)

        forces = [
            self.quad.motors_force[0] + self.command_pitch + self.command_yaw,
            self.quad.motors_force[1] + -self.command_pitch + self.command_yaw,
            self.quad.motors_force[2] + self.command_roll - self.command_yaw,
            self.quad.motors_force[3] + -self.command_roll - self.command_yaw,
        ]
        self.update_forces(forces)

    def step(self):
        self.stabilize()
        self.apply_commands()
        self.quad.step()


if __name__ == '__main__':
    # enable wii remote?
    wm = set_wii_remote()
    if wm:
        import cwiid

    world = World()
    world.setGravity((0, -9.81, 0))
    space = Space()
    contactgroup = JointGroup()

    # draw floor
    floor = GeomPlane(space, (0, 1, 0), -1)
    box(pos=(0, -1, 0), width=2, height=0.01, length=2)

    # Draw Quad
    quad = Quad(world, space, pos=(0, 0, 0))

    # Init Algorithm
    stable = Stable(quad)

    # stop autoscale of the camera
    scene.autoscale = False

    # Initial noise
    #quad.motors[2].addForce((0.5, 1, 0))

    # Collision callback
    def near_callback(args, geom1, geom2):
        """Callback function for the collide() method.
        This function checks if the given geoms do collide and
        creates contact joints if they do.
        """
        # Check if the objects do collide
        contacts = collide(geom1, geom2)

        # Create contact joints
        world, contactgroup = args
        for c in contacts:
            c.setBounce(0.2)
            c.setMu(5000)
            j = ContactJoint(world, contactgroup, c)
            j.attach(geom1.getBody(), geom2.getBody())

    # Do the simulation...
    total_time = 0.0
    dt = 0.04
    while True:
        rate(dt*1000)

        # Control Quad if controls are enabled
        if wm:
            if wm.state['buttons'] & cwiid.BTN_LEFT:
                stable.command_yaw = 1
            if wm.state['buttons'] & cwiid.BTN_RIGHT:
                stable.command_yaw = -1
            if wm.state['buttons'] & cwiid.BTN_1:
                stable.command_acceleration = 1
            if wm.state['buttons'] & cwiid.BTN_2:
                stable.command_acceleration = -1
            if wm.state['buttons'] & cwiid.BTN_A and wm.state['acc']:
                p = (wm.state['acc'][1] - 125.) / 125.
                r = (wm.state['acc'][0] - 125.) / 125.
                stable.command_pitch = -p
                stable.command_roll = r
            if wm.state['buttons'] & cwiid.BTN_B and wm.state['acc']:
                a = (wm.state['acc'][1] - 125.) / 125.
                stable.command_acceleration = a * 10
            if wm.state['buttons'] & cwiid.BTN_HOME:
                wm.close()
                break
            if not wm.state['buttons']:
                stable.command_pitch = 0
                stable.command_roll = 0
                stable.command_yaw = 0
                stable.command_acceleration = 0

        print "%1.2fsec: pos=(%6.3f, %6.3f, %6.3f) vel=(%6.3f, %6.3f, %6.3f) pry=(%6.3f, %6.3f, %6.3f)" % \
              (total_time, quad.pos[0], quad.pos[1], quad.pos[2],
                        quad.vel[0], quad.vel[1], quad.vel[2],
                        quad.pitch, quad.roll, quad.yaw)
        print "power=(%6.3f, %6.3f, %6.3f, %6.3f)" % (quad.motors_force[0], quad.motors_force[1], quad.motors_force[2], quad.motors_force[3])

        # Detect collisions
        space.collide((world, contactgroup), near_callback)
        stable.step()
        world.step(dt)
        contactgroup.empty()

        # point camera to quad
        scene.center = quad.pos

        total_time+=dt
