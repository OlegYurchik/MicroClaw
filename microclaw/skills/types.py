from pydantic import constr


SkillNameType = constr(pattern=r"^[a-z0-9-]{1,64}$")
