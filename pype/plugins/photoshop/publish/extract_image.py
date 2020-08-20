import os

import pype.api
from avalon import photoshop

from pype.modules.websocket_server.clients.photoshop_client import (
    PhotoshopClientStub
)


class ExtractImage(pype.api.Extractor):
    """Produce a flattened image file from instance

    This plug-in takes into account only the layers in the group.
    """

    label = "Extract Image"
    hosts = ["photoshop"]
    families = ["image"]
    formats = ["png", "jpg"]

    def process(self, instance):

        staging_dir = self.staging_dir(instance)
        self.log.info("Outputting image to {}".format(staging_dir))

        # Perform extraction
        photoshop_client = PhotoshopClientStub()
        files = {}
        with photoshop.maintained_selection():
            self.log.info("Extracting %s" % str(list(instance)))
            with photoshop.maintained_visibility():
                # Hide all other layers.
                extract_ids = set([ll.id for ll in photoshop_client.
                                   get_layers_in_layers([instance[0]])])

                for layer in photoshop_client.get_layers():
                    # limit unnecessary calls to client
                    if layer.visible and layer.id not in extract_ids:
                        photoshop_client.set_visible(layer.id,
                                                     False)
                    if not layer.visible and layer.id in extract_ids:
                        photoshop_client.set_visible(layer.id,
                                                     True)

                save_options = []
                if "png" in self.formats:
                    save_options.append('png')
                if "jpg" in self.formats:
                    save_options.append('jpg')

                file_basename = os.path.splitext(
                    photoshop_client.get_active_document_name()
                )[0]
                for extension in save_options:
                    _filename = "{}.{}".format(file_basename, extension)
                    files[extension] = _filename

                    full_filename = os.path.join(staging_dir, _filename)
                    photoshop_client.saveAs(full_filename,
                                            extension,
                                            True)

        representations = []
        for extension, filename in files.items():
            representations.append({
                "name": extension,
                "ext": extension,
                "files": filename,
                "stagingDir": staging_dir
            })
        instance.data["representations"] = representations
        instance.data["stagingDir"] = staging_dir

        self.log.info(f"Extracted {instance} to {staging_dir}")
