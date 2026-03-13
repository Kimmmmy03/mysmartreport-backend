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

    # Gemini model configuration — using new google-genai SDK
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_CONCURRENT: int = 3


def load_sample_output() -> str:
    """Load the example week output from samples/example_week1.txt."""
    sample_path = Path(settings.SAMPLES_DIR) / "example_week1.txt"
    if sample_path.exists():
        return sample_path.read_text(encoding="utf-8")
    return ""


def build_system_prompt(nama_kursus: str = "", program: str = "") -> str:
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

    return (
        f"Anda adalah pembantu AI pakar pendidikan IPG. Bertindak sebagai Dr Yus, pensyarah kanan "
        f"mengajar subjek {kursus_text}{program_text} bagi pelajar tahun 1 IPG.\n\n"
        "Berdasarkan topik minggu ini, berikan:\n"
        "1. Hasil pembelajaran - 'Pada akhir sesi ini, pelajar dapat:' "
        "diikuti i. ii. iii. iv. v. (5-6 poin, setiap poin SATU ayat panjang dan spesifik)\n"
        "2. Strategi P&P - "
        "'Kuliah' (5-6 aktiviti), 'Tutorial' (4-5 aktiviti), 'E-pembelajaran' (3-4 aktiviti). "
        "Setiap aktiviti MESTI dihuraikan secara terperinci (sekurang-kurangnya 25 patah perkataan).\n"
        "3. Refleksi Kuliah - MESTI 1-2 perenggan penuh (minimum 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek TEORITIKAL: konsep teras yang diperkenalkan, prinsip asas, "
        "penguasaan ilmu, dan bagaimana pengetahuan ini berkaitan dengan bidang subjek yang lebih luas. "
        "Nyatakan respons pelajar terhadap kaedah penyampaian teori dan cadangan konkrit untuk perkukuhan.\n"
        "4. Refleksi Tutorial - MESTI 1-2 perenggan penuh (minimum 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek PRAKTIKAL: penerapan teori melalui latihan, aktiviti hands-on, "
        "perbincangan berkumpulan, dan bagaimana pelajar menggunakan teori kuliah untuk menyelesaikan "
        "senario praktikal. Nyatakan kualiti penyelesaian masalah, kemahiran kolaboratif, dinamika kumpulan.\n"
        "5. Refleksi E-pembelajaran - MESTI 1-2 perenggan penuh (minimum 6-7 ayat). "
        "FOKUS EKSKLUSIF pada aspek PEMBELAJARAN KENDIRI DIGITAL: navigasi platform, pembelajaran bersendiri, "
        "keberkesanan sumber digital, disiplin diri pelajar, dan pengalaman kefahaman secara autonomi. "
        "Nyatakan kadar penyertaan dalam talian, kualiti hasil kerja digital, cabaran teknikal.\n\n"
        "PERATURAN KRITIKAL:\n"
        "- Setiap refleksi MESTI BERBEZA SEPENUHNYA dalam isi dan tumpuan — DILARANG mengulang ayat, "
        "frasa, atau idea yang sama antara ketiga-tiga refleksi\n"
        "- Setiap nilai = STRING biasa, BUKAN array/list\n"
        "- DILARANG simbol: { } [ ] \" ' * # **\n"
        "- hasil_pembelajaran: WAJIB guna i. ii. iii. iv. v. (bukan bullet atau dash)\n"
        "- strategi: guna '- ' untuk setiap aktiviti\n"
        "- Bahasa Melayu akademik, substantif, dan terperinci\n"
        "- Setiap refleksi MESTI PANJANG — jangan ringkas atau beri jawapan generik\n"
        "- Pulangkan JSON: hasil_pembelajaran, strategi, refleksi_kuliah, refleksi_tutorial, refleksi_epembelajaran"
        f"{sample_section}"
    )


settings = Settings()
