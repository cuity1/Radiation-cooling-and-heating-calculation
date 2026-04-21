"""
Seed the Q&A database with an initial question + answer.
Run from the Radiation-cooling-and-heating-calculation directory:

    python -m webapi.seed_qa

or from project root:

    python -m webapi.seed_qa
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

# Ensure webapi package is importable
sys.path.insert(0, str(__file__).rsplit("/", 1)[0])

from webapi.db.models import Base, QaAnswer, QaQuestion, User, USER_TIER_PERMANENT_PRO
from webapi.db.session import engine, SessionLocal
from webapi.services.auth_service import hash_password

# ─── Content ──────────────────────────────────────────────────────────────────

QUESTION_TITLE = "辐射制冷：宽带发射 vs 选择性发射，哪个更好？"
QUESTION_BODY = """我在看文献时发现，两种设计思路都有：

1. **宽带发射（Broadband emitter）**：3–25 μm 基本都高发射
2. **选择性发射（Selective emitter）**：只在 8–13 μm 大气窗口高发射

这两种看起来矛盾，到底应该选哪个？
"""

ANSWER_BODY = """## 一、讨论的核心结论（先给直接答案）

**是的：不需要整个 MIR（3–25 μm）都高发射。**

实际上存在两条"都正确"的设计路径：

### 1️⃣ 宽带发射（Broadband emitter）

* 3–25 μm基本都高发射
* 特点：
  * 👉 辐射功率大
  * 👉 更容易降温（特别是高于环境温度时）

---

### 2️⃣ 选择性发射（Selective emitter）

* 只在**大气窗口（8–13 μm）高发射**
* 在其他MIR波段（特别是3–8 μm、>13 μm）**低发射（=低吸收）**
* 特点：
  * 👉 减少吸收环境回辐射
  * 👉 更容易实现**亚环境冷却（T < Tamb）**

---

## 二、为什么会有"看起来矛盾"的两种说法？

关键不是"发多少"，而是：

> 🔥 **净辐射功率 = 自己发出去 − 从环境吸回来**

可以写成一个物理本质表达（不用死记）：

$$P_{net} = \\int \\epsilon(\\lambda)\\left[ B(T_{obj}) - B(T_{env}) \\cdot \\tau_{atm}(\\lambda) \\right] d\\lambda$$

👉 这里真正决定成败的是：

* ε(λ)：你设计的发射率
* τ(λ)：大气透过率

---

## 三、跨一步理解（这才是本质）

## 🌍 大气不是"透明背景"，而是一个"有选择的辐射体"

| 波段      | 大气行为           |
| ------- | -------------- |
| 8–13 μm | 高透过（≈可以辐射到外太空） |
| 3–8 μm  | 强吸收 + 强再辐射     |
| >13 μm  | 也是吸收明显         |

👉 关键推论：

### ❗ 在非窗口波段：

你发出去 ≈ 马上被大气吸收
→ 然后**以环境温度再辐射回来**

👉 等价于：

> 你在和"环境"交换热，而不是和"宇宙"交换热

---

## 四、于是两种策略本质区别

## ✅ 宽带发射 = "多发总没错"

* 优点：总辐射功率大
* 问题：
  ❌ 也增强了环境吸收（反噬）

👉 类似：

> 你开了很多窗，但有些窗外是"热源"

---

## ✅ 选择性发射 = "只往冷的地方发"

* 只在 8–13 μm 发
* 避开其他波段

👉 本质是：

> **光谱匹配热力学通道**

---

## 五、一个更"反常识"的统一解释（重点）

你可以用一个更高级的视角理解：

## 👉 这不是"材料发射率设计问题"，而是：

> 🔥 **系统级能量流匹配问题**

---

### 🔁 换句话说：

你设计的不是材料，而是：

> **"物体—大气—宇宙"三者之间的能量通道耦合**

---

### 📌 重新定义目标函数：

不是：

> 发射率越高越好 ❌

而是：

$$\\maximize \\ \\int \\epsilon(\\lambda) \\cdot \\tau_{atm}(\\lambda)$$

👉 只在**能逃逸的通道上发射**

---

## 六、回答你当时的困惑（关键点）

你说：

> "我的材料在大气窗口高发射，但整体MIR低，我还要不要提高？"

### ✔ 答案：

👉 **不一定要提高！甚至可能是优势**

如果你的目标是：

### 🌙 亚环境冷却（sub-ambient cooling）

✔ 当前结构是合理甚至优越的

---

## 七、人体热管理那一段，也帮你梳理一下

你们后面讨论其实已经触及一个更深层分类：

## 两种完全不同机制：

### 1️⃣ 材料自己辐射

* → 要高发射率

### 2️⃣ 让人体直接辐射（透过材料）

* → 要高透过率

👉 本质区别：

| 类型    | 主体    |
| ----- | ----- |
| 高发射材料 | 材料在散热 |
| 高透过材料 | 人体在散热 |

---

"""


def seed() -> None:
    # 1. Create all tables (idempotent — safe to re-run)
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables ready")

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 2. Ensure admin user exists
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("ustcadmin"),
                role="admin",
                tier=USER_TIER_PERMANENT_PRO,
                pro_expires_at=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"[OK] Created user: admin (id={admin.id})")
        else:
            print(f"[OK] User exists: admin (id={admin.id})")

        # 3. Check if question already exists (avoid duplicates on re-run)
        existing = (
            db.query(QaQuestion)
            .filter(QaQuestion.title == QUESTION_TITLE)
            .first()
        )
        if existing:
            print(f"[SKIP] Question already exists (id={existing.id})")
            return

        # 4. Insert question
        question = QaQuestion(
            title=QUESTION_TITLE,
            body=QUESTION_BODY,
            created_by_user_id=admin.id,
            created_at=now,
            updated_at=now,
            is_deleted=False,
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        print(f"[OK] Question inserted (id={question.id})")

        # 5. Insert answer
        answer = QaAnswer(
            question_id=question.id,
            body=ANSWER_BODY,
            created_by_user_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        db.add(answer)

        # Update question updated_at to bring it to top of list
        question.updated_at = now

        db.commit()
        db.refresh(answer)
        print(f"[OK] Answer inserted (id={answer.id})")

        print("\n[DONE] Q&A seed data imported successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
