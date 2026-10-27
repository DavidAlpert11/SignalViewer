"""Investigation step 5: what tells runs apart - constant signals and numbers in the file name."""
from app.store import Store


def test_constants_and_name_numbers(tmp_path):
    p = tmp_path / "mc_mass2.4_wind=8_run_012.csv"
    p.write_text("Time,Payload_kg,Speed\n0,2.4,1\n1,2.4,3\n2,2.4,2\n")
    st = Store()
    rid = st.open_file(str(p)).id
    ps = st.run_params()[rid]
    assert ps["Payload_kg"] == 2.4 and "Speed" not in ps
    assert ps["mass"] == 2.4 and ps["wind"] == 8 and ps["run"] == 12
