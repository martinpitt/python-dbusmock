%global modname dbusmock

Name:             python-%{modname}
Version:          0.23.0
Release:          1%{?dist}
Summary:          Mock D-Bus objects

License:          LGPL-3.0-or-later
URL:              https://pypi.python.org/pypi/python-dbusmock
Source0:          https://files.pythonhosted.org/packages/source/p/%{name}/python_%{modname}-%{version}.tar.gz

BuildArch:        noarch
BuildRequires:    git
BuildRequires:    python3-devel
BuildRequires:    python3-gobject
BuildRequires:    python3-pytest
BuildRequires:    dbus-x11
BuildRequires:    upower

%global _description\
With this program/Python library you can easily create mock objects on\
D-Bus. This is useful for writing tests for software which talks to\
D-Bus services such as upower, systemd, ConsoleKit, gnome-session or\
others, and it is hard (or impossible without root privileges) to set\
the state of the real services to what you expect in your tests.

%description %_description

%package -n python3-dbusmock
Summary: %summary (Python3)
Requires:         python3-dbus, python3-gobject, dbus-x11
%description -n python3-dbusmock %_description

%prep
%autosetup -n python_%{modname}-%{version}
rm -rf python-%{modname}.egg-info

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l dbusmock

%check
%{__python3} -m unittest -v

%files -n python3-dbusmock -f %{pyproject_files}

%doc README.md COPYING

%changelog
