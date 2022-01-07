import locale
import os
import re
import subprocess
import sys

working_directory = os.getcwd()

preferred_encoding = locale.getpreferredencoding()

types_name_matcher = re.compile(
    'Cannot find module \'(.+?)\' or its corresponding type declarations\\.'
    '|Could not find a declaration file for module \'(.+?)\'\\.')

other_version_matcher = re.compile('^v\\d+$')


def obtain_types_name(error_message: str) -> str | None:
    match = types_name_matcher.search(error_message)
    if not match:
        return None

    return match.group(1) or match.group(2)


def find_other_versions(types_name: str) -> list[str]:
    path_to_scan = os.path.join(working_directory, 'types', types_name)
    if not os.path.exists(path_to_scan):
        return []

    immediate_sub_directories = map(lambda file: file.name,
                                    filter(lambda file: file.is_dir(), os.scandir(path_to_scan)))
    return list(filter(lambda dir_name: other_version_matcher.search(dir_name), immediate_sub_directories))


def checkout_types(types_name: str):
    os.chdir(working_directory)
    while os.system(f'git sparse-checkout add types/{types_name}') != 0:
        continue


def npm_install(types_name: str = None, version: str = None):
    install_directory = working_directory if not types_name \
        else os.path.join(working_directory, 'types', types_name) if not version \
        else os.path.join(working_directory, 'types', types_name, version)

    if not os.path.exists(install_directory):
        return

    os.chdir(install_directory)
    while os.system('npm install') != 0:
        continue


def capture_test_error_message(types_name: str, version: str = None):
    test_unit = f"{types_name}/{version}" if version else types_name
    os.chdir(working_directory)
    result = subprocess.run(f'npm run test {test_unit}',
                            shell=True,
                            capture_output=True)
    sys.stdout.buffer.write(result.stdout)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.write(result.stderr)
    sys.stderr.buffer.flush()
    if result.returncode == 0:
        return None
    else:
        return result.stderr.decode(encoding=preferred_encoding)


def obtain_missing_types_name(error_message: str) -> list[str]:
    lines = error_message.splitlines(keepends=False)
    return [name for name in map(lambda l: obtain_types_name(l), lines) if name]


def fixup_dependencies(types_name, version=None, skip_test=False):
    if not version:
        checkout_types(types_name)
        for other_version in find_other_versions(types_name):
            fixup_dependencies(types_name, other_version)

    print("================================================================================")
    print(f'Fixup {types_name} {version or "latest"}')
    print("================================================================================")

    npm_install(types_name, version)

    if skip_test:
        return

    error_message = capture_test_error_message(types_name, version)
    while error_message:
        for missing_types_name in obtain_missing_types_name(error_message):
            fixup_dependencies(missing_types_name)
        error_message = capture_test_error_message(types_name, version)


if __name__ == '__main__':
    types_name = sys.argv[1]

    npm_install()
    fixup_dependencies('node', skip_test=True)
    fixup_dependencies(types_name)
