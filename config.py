"""
MySmartReport Backend — Configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TEMPLATE_PATH: str = os.getenv("TEMPLATE_PATH", "templates/template.xlsx")
    SAMPLES_DIR: str = os.getenv("SAMPLES_DIR", "samples")

    ADMIN_EMAILS: list = [
        "akmalhakimi1150@gmail.com",
    ]

    # Gemini model configuration — using new google-genai SDK
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_CONCURRENT: int = 3


def load_sample_output() -> str:
    """Load the example week output from samples/example_week1.txt."""
    sample_path = Path(settings.SAMPLES_DIR) / "example_week1.txt"
    if sample_path.exists():
        return sample_path.read_text(encoding="utf-8")
    return ""


def build_system_prompt(nama_kursus: str = "", program: str = "", detail_level: str = "normal") -> str:
    """
    Build a dynamic system prompt injecting course name, program,
    and sample output as context for the AI.
    """
    kursus_text = nama_kursus if nama_kursus else "psikologi pembelajaran"
    program_text = f" dalam program {program}" if program else ""

    sample = load_sample_output()
    sample_section = ""
    if sample:
        sample_section = (
            "\n\n--- CONTOH KELUARAN MINGGU 1 (RUJUKAN FORMAT) ---\n"
            f"{sample}\n"
            "--- TAMAT CONTOH ---\n\n"
            "Ikut format dan gaya penulisan yang SAMA seperti contoh di atas. "
            "Pastikan jawapan mengikut struktur yang sama."
        )

    # Detail level adjustments
    if detail_level == "terperinci":
        hasil_desc = (
            "1. Hasil pembelajaran - 'Pada akhir sesi ini, pelajar dapat:' "
            "diikuti i. ii. iii. iv. v. vi. vii. (7-8 poin, setiap poin SATU ayat PANJANG dan sangat spesifik)\n"
        )
        strategi_desc = (
            "2. Strategi P&P - "
            "'Kuliah' (7-8 aktiviti), 'Tutorial' (5-6 aktiviti), 'E-pembelajaran' (4-5 aktiviti). "
            "Setiap aktiviti MESTI dihuraikan secara SANGAT terperinci (sekurang-kurangnya 35 patah perkataan).\n"
        )
        refleksi_desc = (
            "3. Refleksi Kuliah - MESTI 2-3 perenggan penuh (minimum 8-10 ayat). "
            "FOKUS EKSKLUSIF pada aspek TEORITIKAL: konsep teras yang diperkenalkan, prinsip asas, "
            "penguasaan ilmu, bagaimana pengetahuan ini berkaitan dengan bidang subjek yang lebih luas, "
            "dan cadangan penambahbaikan yang mendalam. "
            "Nyatakan respons pelajar terhadap kaedah penyampaian teori dan cadangan konkrit untuk perkukuhan.\n"
            "4. Refleksi Tutorial - MESTI 2-3 perenggan penuh (minimum 8-10 ayat). "
            "FOKUS EKSKLUSIF pada aspek PRAKTIKAL: penerapan teori melalui latihan, aktiviti hands-on, "
            "perbincangan berkumpulan, senario simulasi, dan bagaimana pelajar menggunakan teori kuliah untuk menyelesaikan "
            "senario praktikal. Nyatakan kualiti penyelesaian masalah, kemahiran kolaboratif, dinamika kumpulan.\n"
            "5. Refleksi E-pembelajaran - MESTI 2-3 perenggan penuh (minimum 8-10 ayat). "
            "FOKUS EKSKLUSIF pada aspek PEMBELAJARAN KENDIRI DIGITAL: navigasi platform, pembelajaran bersendiri, "
            "keberkesanan sumber digital, disiplin diri pelajar, dan pengalaman kefahaman secara autonomi. "
            "Nyatakan kadar penyertaan dalam talian, kualiti hasil kerja digital, cabaran teknikal.\n\n"
        )
        refleksi_rule = "- Setiap refleksi MESTI SANGAT PANJANG dan MENDALAM — 2-3 perenggan penuh, jangan ringkas\n"
    else:  # normal (default)
        hasil_desc = (
            "1. Hasil pembelajaran - 'Pada akhir sesi ini, pelajar dapat:' "
            "diikuti i. ii. iii. iv. v. (5-6 poin, setiap poin SATU ayat yang tepat dan spesifik)\n"
        )
        strategi_desc = (
            "2. Strategi P&P - "
            "'Kuliah' (5-6 aktiviti), 'Tutorial' (4-5 aktiviti), 'E-pembelajaran' (3-4 aktiviti). "
            "Setiap aktiviti MESTI dihuraikan dengan jelas (sekurang-kurangnya 20 patah perkataan).\n"
        )
        refleksi_desc = (
            "3. Refleksi Kuliah - MESTI 1-2 perenggan (5-7 ayat). "
            "FOKUS EKSKLUSIF pada aspek TEORITIKAL: konsep teras yang diperkenalkan, prinsip asas, "
            "penguasaan ilmu, bagaimana pengetahuan ini berkaitan dengan bidang subjek yang lebih luas, "
            "dan cadangan penambahbaikan. "
            "Nyatakan respons pelajar terhadap kaedah penyampaian teori dan cadangan untuk perkukuhan.\n"
            "4. Refleksi Tutorial - MESTI 1-2 perenggan (5-7 ayat). "
            "FOKUS EKSKLUSIF pada aspek PRAKTIKAL: penerapan teori melalui latihan, aktiviti hands-on, "
            "perbincangan berkumpulan, senario simulasi, dan bagaimana pelajar menggunakan teori kuliah untuk menyelesaikan "
            "senario praktikal. Nyatakan kualiti penyelesaian masalah, kemahiran kolaboratif, dinamika kumpulan.\n"
            "5. Refleksi E-pembelajaran - MESTI 1-2 perenggan (5-7 ayat). "
            "FOKUS EKSKLUSIF pada aspek PEMBELAJARAN KENDIRI DIGITAL: navigasi platform, pembelajaran bersendiri, "
            "keberkesanan sumber digital, disiplin diri pelajar, dan pengalaman kefahaman secara autonomi. "
            "Nyatakan kadar penyertaan dalam talian, kualiti hasil kerja digital, cabaran teknikal.\n\n"
        )
        refleksi_rule = "- Setiap refleksi MESTI 1-2 perenggan padat (5-7 ayat). Jangan terlalu ringkas.\n"

    return (
        f"Anda adalah pembantu AI pakar pendidikan IPG. Bertindak sebagai Dr Yus, pensyarah kanan "
        f"mengajar subjek {kursus_text}{program_text} bagi pelajar tahun 1 IPG.\n\n"
        "Berdasarkan topik minggu ini, berikan:\n"
        f"{hasil_desc}"
        f"{strategi_desc}"
        f"{refleksi_desc}"
        "PERATURAN KRITIKAL:\n"
        "- Setiap refleksi MESTI BERBEZA SEPENUHNYA dalam isi dan tumpuan — DILARANG mengulang ayat, "
        "frasa, atau idea yang sama antara ketiga-tiga refleksi\n"
        "- Setiap nilai = STRING biasa, BUKAN array/list\n"
        "- DILARANG simbol: { } [ ] \" ' * # **\n"
        "- hasil_pembelajaran: WAJIB guna i. ii. iii. iv. v. (bukan bullet atau dash)\n"
        "- strategi: guna '- ' untuk setiap aktiviti\n"
        "- Bahasa Melayu akademik, substantif, dan terperinci\n"
        f"{refleksi_rule}"
        "- Pulangkan JSON: hasil_pembelajaran, strategi, refleksi_kuliah, refleksi_tutorial, refleksi_epembelajaran"
        f"{sample_section}"
    )


settings = Settings()
