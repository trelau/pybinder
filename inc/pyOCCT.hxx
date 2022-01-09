/*
This file is part of pyOCCT which provides Python bindings to the OpenCASCADE
geometry kernel.

Copyright (C) 2016-2018  Laughlin Research, LLC
Copyright (C) 2019-2022  Trevor Laughlin and the pyOCCT contributors

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Lesser General Public
License as published by the Free Software Foundation; either
version 2.1 of the License, or (at your option) any later version.

This library is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public
License along with this library; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
*/
#pragma once

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
	#include<Windows.h>
#endif

#include <pybind11/pybind11.h>

#include <Standard_Handle.hxx>

namespace py = pybind11;

// Use opencascade::handle as holder type for Standard_Transient types
PYBIND11_DECLARE_HOLDER_TYPE(T, opencascade::handle<T>, true);

// Use a shared_ptr for everything else and one with a deleter (credit OCP)
template<typename T, template<typename> typename Deleter = std::default_delete>
struct shared_ptr : public std::shared_ptr<T> {
	explicit shared_ptr(T* t = nullptr) : std::shared_ptr<T>(t, Deleter<T>()) {};
	void reset(T* t = nullptr) { std::shared_ptr<T>::reset(t, Deleter<T>()); };
};

template<typename T> struct nodelete {
	void operator()(T* p) const {};
};

template<typename T> using shared_ptr_nodelete = shared_ptr<T, nodelete>;

PYBIND11_DECLARE_HOLDER_TYPE(T, shared_ptr<T>);
PYBIND11_DECLARE_HOLDER_TYPE(T, shared_ptr_nodelete<T>);
