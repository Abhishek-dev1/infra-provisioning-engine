terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.azure_location
  tags     = var.tags
}

resource "azurerm_virtual_network" "vnet" {
  name                = "${var.job_name}-vnet"
  address_space       = ["10.1.0.0/16"]
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "k8s-nodes-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.1.1.0/24"]
}

resource "azurerm_network_interface" "nic" {
  count               = length(var.nodes)
  name                = "${var.nodes[count.index].name}-nic"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "vms" {
  count                           = length(var.nodes)
  name                            = var.nodes[count.index].name
  resource_group_name             = azurerm_resource_group.rg.name
  location                        = azurerm_resource_group.rg.location
  size                            = var.nodes[count.index].vm_size
  admin_username                  = "azureuser"
  network_interface_ids           = [azurerm_network_interface.nic[count.index].id]
  custom_data                     = base64encode(var.nodes[count.index].custom_data)
  disable_password_authentication = true

  admin_ssh_key {
    username   = "azureuser"
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.nodes[count.index].os_disk_size_gb
  }

  source_image_reference {
    publisher = split(":", var.nodes[count.index].image_urn)[0]
    offer     = split(":", var.nodes[count.index].image_urn)[1]
    sku       = split(":", var.nodes[count.index].image_urn)[2]
    version   = split(":", var.nodes[count.index].image_urn)[3]
  }

  tags = var.tags
}
