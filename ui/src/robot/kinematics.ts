import { Euler, Matrix4, Quaternion, Vector3 } from "three";

const HEAD_Z_OFFSET = 0.177;

type Joint = {
  parent: string;
  child: string;
  origin: Matrix4;
  axis: Vector3 | null;
};

export type JointValues = Record<string, number>;

const numbers = (text: string) => text.split(/\s+/).map(Number) as [number, number, number];

function position(m: Matrix4): Vector3 {
  return new Vector3().setFromMatrixPosition(m);
}

export class StewartSolver {
  private joints = new Map<string, Joint>();
  private byChild = new Map<string, string>();

  constructor(urdf: Document) {
    for (const el of urdf.querySelectorAll("robot > joint")) {
      const o = el.querySelector("origin");
      const xyz = numbers(o?.getAttribute("xyz") ?? "0 0 0");
      const rpy = numbers(o?.getAttribute("rpy") ?? "0 0 0");
      const origin = new Matrix4().compose(
        new Vector3(...xyz),
        new Quaternion().setFromEuler(new Euler(...rpy, "ZYX")),
        new Vector3(1, 1, 1),
      );
      const axis = el.querySelector("axis")?.getAttribute("xyz");
      const joint: Joint = {
        parent: el.querySelector("parent")!.getAttribute("link")!,
        child: el.querySelector("child")!.getAttribute("link")!,
        origin,
        axis: axis ? new Vector3(...numbers(axis)) : null,
      };
      const name = el.getAttribute("name")!;
      this.joints.set(name, joint);
      this.byChild.set(joint.child, name);
    }
  }

  private joint(name: string): Joint {
    const j = this.joints.get(name);
    if (!j) throw new Error(`URDF has no joint ${name}`);
    return j;
  }

  fk(link: string, q: JointValues): Matrix4 {
    const chain: string[] = [];
    for (let name = this.byChild.get(link); name; name = this.byChild.get(this.joint(name).parent)) {
      chain.push(name);
    }
    const t = new Matrix4();
    const r = new Matrix4();
    for (const name of chain.reverse()) {
      const j = this.joint(name);
      t.multiply(j.origin);
      if (j.axis) t.multiply(r.makeRotationAxis(j.axis, q[name] ?? 0));
    }
    return t;
  }

  solve(headPose: number[][], headJoints: number[]): JointValues {
    const q: JointValues = { yaw_body: headJoints[0] };
    for (let i = 1; i <= 6; i++) q[`stewart_${i}`] = headJoints[i];

    const h = new Matrix4().set(...(headPose.flat() as Parameters<Matrix4["set"]>));
    h.elements[14] += HEAD_Z_OFFSET;
    const head = h.multiply(this.joint("head_frame").origin.clone().invert());

    const swing = (frame: Matrix4, d: Vector3, target: Vector3): Euler => {
      const rot = new Matrix4().extractRotation(frame);
      const local = target.clone().sub(position(frame)).applyMatrix4(rot.transpose());
      const quat = new Quaternion().setFromUnitVectors(d.clone().normalize(), local.normalize());
      return new Euler().setFromQuaternion(quat, "XYZ");
    };
    const set = (prefix: string, e: Euler) => {
      q[`${prefix}_x`] = e.x;
      q[`${prefix}_y`] = e.y;
      q[`${prefix}_z`] = e.z;
    };

    for (let i = 1; i <= 5; i++) {
      const leg = this.fk(`passive_${i}_link_x`, q);
      const anchor = position(head.clone().multiply(this.joint(`closing_${i}_2_frame`).origin));
      const rodEnd = position(this.joint(`closing_${i}_1_frame`).origin);
      set(`passive_${i}`, swing(leg, rodEnd, anchor));
    }

    const headLeg = this.fk("passive_6_link_x", q);
    const headMount = this.joint("passive_7_x").origin;
    set("passive_6", swing(headLeg, position(headMount), position(head)));
    const rod = this.fk("stewart_link_rod_6", q).multiply(headMount);
    const r7 = new Matrix4().extractRotation(rod).transpose().multiply(new Matrix4().extractRotation(head));
    set("passive_7", new Euler().setFromRotationMatrix(r7, "XYZ"));
    return q;
  }
}
